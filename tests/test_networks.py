"""Tests of the UniFi networks handler and how VLAN sensors and options use it."""

from typing import Any

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components.unifi.const import (
    CONF_MORE_OPTIONS,
    CONF_VLAN_SENSORS,
    DOMAIN,
)
from homeassistant.components.unifi.hub.networks import Network
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import ConfigEntryFactoryType, WebsocketMessageMock

from tests.common import MockConfigEntry

SITE = "site_id"

DEFAULT = {
    "_id": "id-default",
    "name": "Default",
    "purpose": "corporate",
    "enabled": True,
    "vlan_enabled": False,
}
NOAH = {
    "_id": "id-noah",
    "name": "noah_vlan11",
    "purpose": "corporate",
    "enabled": True,
    "vlan_enabled": True,
    "vlan": 11,
}
GUEST = {
    "_id": "id-guest",
    "name": "guest_vlan30",
    "purpose": "guest",
    "enabled": True,
    "vlan_enabled": True,
    "vlan": "30",
}
DISABLED = {
    "_id": "id-disabled",
    "name": "disabled_vlan40",
    "purpose": "corporate",
    "enabled": False,
    "vlan_enabled": True,
    "vlan": 40,
}
WAN = {"_id": "id-wan", "name": "Internet 1", "purpose": "wan"}
VPN = {"_id": "id-vpn", "name": "VPN", "purpose": "vpn-client", "enabled": True}
NETWORKS = [DEFAULT, NOAH, GUEST, DISABLED, WAN, VPN]


@pytest.mark.parametrize(
    ("payload", "vlan", "vlan_key", "enabled"),
    [
        pytest.param(DEFAULT, None, "native", True, id="default network"),
        pytest.param(NOAH, 11, "11", True, id="tagged network"),
        pytest.param(GUEST, 30, "30", True, id="vlan as text"),
        pytest.param(DISABLED, 40, "40", False, id="disabled network"),
        pytest.param(WAN, None, None, True, id="wan"),
        pytest.param(VPN, None, None, True, id="vpn"),
        pytest.param({**NOAH, "vlan": "abc"}, None, None, True, id="unreadable vlan"),
        pytest.param(
            {"_id": "x", "name": "x", "purpose": "vlan-only", "vlan_enabled": True},
            None,
            None,
            True,
            id="vlan missing",
        ),
    ],
)
def test_network_model(
    payload: dict[str, Any], vlan: int | None, vlan_key: str | None, enabled: bool
) -> None:
    """Test the properties of a network."""
    network = Network(payload)

    assert network.id == payload["_id"]
    assert network.name == payload["name"]
    assert network.purpose == payload["purpose"]
    assert network.vlan == vlan
    assert network.vlan_key == vlan_key
    assert network.enabled is enabled


@pytest.mark.parametrize("network_payload", [NETWORKS])
async def test_networks_handler(
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test networks are loaded and found by VLAN."""
    networks = config_entry_setup.runtime_data.networks

    assert set(networks) == {network["_id"] for network in NETWORKS}
    assert networks.get_by_vlan_key("11").name == "noah_vlan11"
    assert networks.get_by_vlan_key("30").name == "guest_vlan30"
    assert networks.get_by_vlan_key("native").name == "Default"
    assert networks.get_by_vlan_key("40") is None
    assert networks.get_by_vlan_key("99") is None


@pytest.mark.parametrize("network_payload", [[NOAH]])
async def test_networks_websocket_update(
    config_entry_setup: MockConfigEntry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test networks follow changes sent by the controller."""
    networks = config_entry_setup.runtime_data.networks
    assert networks["id-noah"].name == "noah_vlan11"

    mock_websocket_message(
        message=MessageKey.NETWORK_CONF_UPDATED, data={**NOAH, "name": "renamed"}
    )
    mock_websocket_message(message=MessageKey.NETWORK_CONF_UPDATED, data=GUEST)

    assert networks["id-noah"].name == "renamed"
    assert networks.get_by_vlan_key("30").name == "guest_vlan30"


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_VLAN_SENSORS: ["11", "native", "12"]}]
)
@pytest.mark.parametrize("network_payload", [[DEFAULT, NOAH, WAN]])
async def test_vlan_sensor_devices_named_after_networks(
    device_registry: dr.DeviceRegistry, config_entry_setup: MockConfigEntry
) -> None:
    """Test VLAN devices use the network name, or a generic name if unknown."""
    names = {
        vlan: device_registry.async_get_device_by_identifier(
            (DOMAIN, f"vlan-{SITE}-{vlan}"), config_entry_setup.entry_id
        ).name
        for vlan in ("11", "native", "12")
    }

    assert names == {"11": "noah_vlan11", "native": "Default", "12": "VLAN 12"}


@pytest.mark.parametrize("config_entry_options", [{CONF_VLAN_SENSORS: ["50"]}])
@pytest.mark.parametrize("network_payload", [NETWORKS])
@pytest.mark.parametrize(
    "client_payload", [[{"mac": "00:00:00:00:00:01", "name": "On 99", "vlan": 99}]]
)
async def test_option_flow_vlan_choices_from_networks(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test the options list all enabled networks by name, plus other known VLANs."""
    result = await hass.config_entries.options.async_init(config_entry_setup.entry_id)

    more_options = next(
        value
        for key, value in result["data_schema"].schema.items()
        if key == CONF_MORE_OPTIONS
    )
    vlan_selector = next(
        value
        for key, value in more_options.schema.schema.items()
        if key == CONF_VLAN_SENSORS
    )
    assert vlan_selector.config["options"] == [
        {"value": "11", "label": "noah_vlan11 (11)"},
        {"value": "30", "label": "guest_vlan30 (30)"},
        {"value": "50", "label": "50"},
        {"value": "99", "label": "99"},
        {"value": "native", "label": "Default (native)"},
    ]


@pytest.mark.parametrize("config_entry_options", [{CONF_VLAN_SENSORS: ["11"]}])
async def test_vlan_sensors_without_networks(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Test VLAN sensors work if the controller reports no networks."""
    await config_entry_factory()

    assert hass.states.get("sensor.vlan_11_clients").state == "0"
