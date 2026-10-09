"""UniFi Network per-VLAN sensor tests.

Written for the Home Assistant core test suite: copy to tests/components/unifi/
(scripts/run_core_tests.sh does this) and run with the UniFi test fixtures.
"""

from typing import Any

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.unifi.const import CONF_VLAN_SENSORS
from homeassistant.components.unifi.hub.config import parse_vlan_sensors
from homeassistant.components.unifi.sensor import VLAN_REFRESH_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import async_fire_time_changed


def _client(
    mac: str,
    *,
    vlan: int | str | None = None,
    wired: bool = False,
    last_seen: float | None = None,
    rx: float = 0.0,
    tx: float = 0.0,
) -> dict[str, Any]:
    """Build a client payload. Rates are bytes per second."""
    client: dict[str, Any] = {
        "mac": mac,
        "name": f"Client {mac[-2:]}",
        "oui": "Producer",
        "is_wired": wired,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow())
        if last_seen is None
        else last_seen,
    }
    if vlan is not None:
        client["vlan"] = vlan
    if wired:
        client["wired-rx_bytes-r"] = rx
        client["wired-tx_bytes-r"] = tx
        # Wired clients must be measured on the wired counters only
        client["rx_bytes-r"] = 999_000_000
        client["tx_bytes-r"] = 999_000_000
    else:
        client["essid"] = "SSID"
        client["rx_bytes-r"] = rx
        client["tx_bytes-r"] = tx
    return client


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ()),
        ("11", ("11",)),
        ("11, 12 ,30", ("11", "12", "30")),
        ("11 12 30", ("11", "12", "30")),
        ("Native, 11", ("native", "11")),
        ("011", ("11",)),
        ("11, 11, 011", ("11",)),
        ("0, 4095, abc, -3, 1.5, 12", ("12",)),
        ("1, 4094", ("1", "4094")),
    ],
)
def test_parse_vlan_sensors(value: str, expected: tuple[str, ...]) -> None:
    """Verify the option is parsed leniently and de-duplicated."""
    assert parse_vlan_sensors(value) == expected


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_VLAN_SENSORS: "11, 12, native"}]
)
async def test_vlan_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    mock_websocket_state: WebsocketStateManager,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify the per-VLAN client count and traffic sensors."""
    client_payload += [
        # VLAN 11: one wireless (2 Mbit/s) and one wired (2 Mbit/s) client
        _client("00:00:00:00:00:01", vlan=11, rx=125_000, tx=125_000),
        _client("00:00:00:00:00:02", vlan=11, wired=True, rx=250_000, tx=0),
        # VLAN 12: only a stale client
        _client("00:00:00:00:00:03", vlan=12, last_seen=0),
        # Untagged client
        _client("00:00:00:00:00:04", rx=1_250_000),
        # VLAN that is not monitored
        _client("00:00:00:00:00:05", vlan=99, rx=5_000_000),
    ]
    await config_entry_factory()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6

    assert hass.states.get("sensor.vlan_11_clients").state == "2"
    assert hass.states.get("sensor.vlan_11_traffic").state == "4.0"
    assert hass.states.get("sensor.vlan_12_clients").state == "0"
    assert hass.states.get("sensor.vlan_12_traffic").state == "0.0"
    assert hass.states.get("sensor.native_vlan_clients").state == "1"
    assert hass.states.get("sensor.native_vlan_traffic").state == "10.0"
    assert hass.states.get("sensor.vlan_99_clients") is None

    # A client joins VLAN 12
    mock_websocket_message(
        message=MessageKey.CLIENT,
        data=_client("00:00:00:00:00:03", vlan=12, rx=62_500),
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.vlan_12_clients").state == "1"
    assert hass.states.get("sensor.vlan_12_traffic").state == "0.5"

    # Its traffic changes
    mock_websocket_message(
        message=MessageKey.CLIENT,
        data=_client("00:00:00:00:00:03", vlan=12, rx=125_000),
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.vlan_12_traffic").state == "1.0"

    # The client moves to another VLAN
    mock_websocket_message(
        message=MessageKey.CLIENT,
        data=_client("00:00:00:00:00:03", vlan=11, rx=125_000),
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.vlan_12_clients").state == "0"
    assert hass.states.get("sensor.vlan_11_clients").state == "3"

    # A client stops being seen: dropped on the next periodic refresh
    mock_websocket_message(
        message=MessageKey.CLIENT,
        data=_client("00:00:00:00:00:03", vlan=11, last_seen=0),
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + VLAN_REFRESH_INTERVAL)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.vlan_11_clients").state == "2"

    # Availability follows the controller connection
    await mock_websocket_state.disconnect()
    assert hass.states.get("sensor.vlan_11_clients").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.native_vlan_traffic").state == STATE_UNAVAILABLE

    await mock_websocket_state.reconnect()
    assert hass.states.get("sensor.vlan_11_clients").state == "2"

    # Entities belong to one device per VLAN
    entry = entity_registry.async_get("sensor.vlan_11_clients")
    assert entry.translation_key == "vlan_clients"
    assert (
        entity_registry.async_get("sensor.vlan_11_traffic").device_id == entry.device_id
    )
    assert (
        entity_registry.async_get("sensor.vlan_12_clients").device_id != entry.device_id
    )


async def test_vlan_sensors_disabled_by_default(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify no VLAN sensors are created unless the option is set."""
    client_payload.append(_client("00:00:00:00:00:01", vlan=11))
    await config_entry_factory()
    assert not hass.states.async_entity_ids(SENSOR_DOMAIN)


@pytest.mark.parametrize("config_entry_options", [{CONF_VLAN_SENSORS: "11, 12"}])
async def test_vlan_sensor_options_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_setup: ConfigEntry,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify VLAN sensors are added and removed when the option changes."""
    assert hass.states.get("sensor.vlan_11_clients")
    assert hass.states.get("sensor.vlan_12_clients")
    assert hass.states.get("sensor.vlan_30_clients") is None

    # Add VLAN 30, remove VLAN 11
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_VLAN_SENSORS: "12, 30"}
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.vlan_11_clients") is None
    assert hass.states.get("sensor.vlan_11_traffic") is None
    assert entity_registry.async_get("sensor.vlan_11_clients") is None
    assert hass.states.get("sensor.vlan_12_clients")
    assert hass.states.get("sensor.vlan_30_clients").state == "0"
    assert hass.states.get("sensor.vlan_30_traffic")

    # A removed VLAN can be added back
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_VLAN_SENSORS: "11, 12, 30"}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.vlan_11_clients")

    # All removed
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_VLAN_SENSORS: ""}
    )
    await hass.async_block_till_done()
    assert not hass.states.async_entity_ids(SENSOR_DOMAIN)
