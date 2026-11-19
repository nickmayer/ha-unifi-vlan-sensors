"""Tests of objects that UniFi Network re-creates under new IDs.

An update of UniFi Network can give every network, WLAN and rule a new ID while
Home Assistant stays connected. The copies with the old IDs must go away on the
next fetch, and the lease sensors must not depend on the network IDs.
"""

from copy import deepcopy
from typing import Any

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifi.const import CONF_VLAN_SENSORS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from .test_switch import TRAFFIC_RULE, WLAN

NOAH = {
    "_id": "6869723eaff3c7505f1dd439",
    "name": "noah_vlan11",
    "purpose": "corporate",
    "enabled": True,
    "vlan_enabled": True,
    "vlan": 11,
}
NOAH_NEW_ID = {**NOAH, "_id": "23753da1-fc2b-4b8d-a3ff-d629ed57eaa1"}
DISABLED_VLAN11 = {**NOAH, "_id": "id-old-disabled", "enabled": False}


def _overview(*configurations: dict[str, Any], leases: int = 3) -> list[dict]:
    return [
        {
            "configuration": configuration,
            "statistics": {"dhcp_active_leases": leases, "dhcp_max_leases": 249},
        }
        for configuration in configurations
    ]


@pytest.mark.parametrize("config_entry_options", [{CONF_VLAN_SENSORS: ["11"]}])
@pytest.mark.parametrize("network_payload", [[NOAH]])
@pytest.mark.parametrize(
    "lan_overview_payload",
    [_overview({**DISABLED_VLAN11}, leases=99) + _overview(NOAH_NEW_ID)],
)
async def test_leases_found_by_vlan_when_network_ids_differ(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test the leases match by VLAN, not by the ID of the network handler."""
    await async_update_entity(hass, "sensor.noah_vlan11_leases")
    state = hass.states.get("sensor.noah_vlan11_leases")

    assert state.state == "3"
    assert state.attributes["max_leases"] == 249


def _mock_get(
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    path: str,
    payload: list[dict[str, Any]],
) -> None:
    url = f"https://{config_entry.data['host']}:1234"
    if path.startswith("/v2"):
        json: Any = payload
    else:
        json = {"meta": {"rc": "OK"}, "data": payload}
    aioclient_mock.get(
        f"{url}{path}", json=json, headers={"content-type": "application/json"}
    )


TRAFFIC_RULE_NEW_ID = {**deepcopy(TRAFFIC_RULE), "_id": "972fb9b8-ca18-46fb-a893-x"}


@pytest.mark.parametrize("traffic_rule_payload", [[TRAFFIC_RULE]])
async def test_vanished_rule_is_removed_on_poll(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test a rule the controller lists under a new ID replaces the old entity."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.traffic_rules
    )
    old_entity_id = "switch.unifi_network_test_traffic_rule"
    assert hass.states.get(old_entity_id)

    aioclient_mock.clear_requests()
    _mock_get(
        aioclient_mock,
        config_entry_setup,
        f"/v2/api/site/{config_entry_setup.data['site']}/trafficrules",
        [TRAFFIC_RULE_NEW_ID],
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert TRAFFIC_RULE["_id"] not in hub.api.traffic_rules
    assert TRAFFIC_RULE_NEW_ID["_id"] in hub.api.traffic_rules
    assert entity_registry.async_get(old_entity_id) is None
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1


@pytest.mark.parametrize("traffic_rule_payload", [[TRAFFIC_RULE]])
async def test_empty_list_does_not_remove_rules(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test an empty answer, as from a starting application, keeps the rules."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.traffic_rules
    )

    aioclient_mock.clear_requests()
    _mock_get(
        aioclient_mock,
        config_entry_setup,
        f"/v2/api/site/{config_entry_setup.data['site']}/trafficrules",
        [],
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert TRAFFIC_RULE["_id"] in hub.api.traffic_rules
    assert hass.states.get("switch.unifi_network_test_traffic_rule")


WLAN_NEW_ID = {**deepcopy(WLAN), "_id": "6f3e9e2e-a245-407d-af7c-04984166bcf8"}


@pytest.mark.parametrize("wlan_payload", [[WLAN]])
async def test_vanished_wlan_is_removed_on_resync(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test the refetch after a lost connection drops WLANs with old IDs."""
    hub = config_entry_setup.runtime_data
    assert hass.states.get("switch.ssid_1_enabled")

    aioclient_mock.clear_requests()
    _mock_get(
        aioclient_mock,
        config_entry_setup,
        f"/api/s/{config_entry_setup.data['site']}/rest/wlanconf",
        [WLAN_NEW_ID],
    )
    await hub.entity_loader.async_resync()
    await hass.async_block_till_done()

    assert set(dict(hub.api.wlans.items())) == {WLAN_NEW_ID["_id"]}
    entry = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "unifi", f"wlan-{WLAN['_id']}"
    )
    assert entry is None
    assert entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "unifi", f"wlan-{WLAN_NEW_ID['_id']}"
    )


@pytest.mark.parametrize("client_payload", [[{"mac": "00:00:00:00:00:01"}]])
async def test_clients_are_not_pruned(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test a client missing from the active list stays known."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(hub.api.clients)

    aioclient_mock.clear_requests()
    _mock_get(
        aioclient_mock,
        config_entry_setup,
        f"/api/s/{config_entry_setup.data['site']}/stat/sta",
        [{"mac": "00:00:00:00:00:02"}],
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert "00:00:00:00:00:01" in hub.api.clients

