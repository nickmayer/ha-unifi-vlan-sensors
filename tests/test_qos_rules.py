"""Tests of the QoS rule switches (throttle rules after the Policy Engine migration)."""

from copy import deepcopy
from typing import Any

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifi.qos_rules import qos_rules
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

# As UniFi Network lists a migrated throttle rule
QOS_RULE = {
    "_id": "e0a743e3-9e20-45b2-a34f-c0083ac16bab",
    "destination": {"matching_target": "ANY", "port_matching_type": "ANY"},
    "download_burst": "OFF",
    "download_limit_kbps": 128,
    "enabled": False,
    "index": 10003,
    "name": "Throttle Noah Internet",
    "objective": "LIMIT_AND_PRIORITIZE",
    "schedule": {
        "date_end": "2026-10-16",
        "date_start": "2026-10-09",
        "mode": "ALWAYS",
        "repeat_on_days": [],
        "time_all_day": False,
        "time_range_end": "12:00",
        "time_range_start": "09:00",
    },
    "source": {
        "matching_target": "NETWORK",
        "network_ids": ["23753da1-fc2b-4b8d-a3ff-d629ed57eaa1"],
    },
    "upload_burst": "OFF",
    "upload_limit_kbps": 128,
}
ENTITY_ID = "switch.unifi_network_throttle_noah_internet"


def _url(config_entry: MockConfigEntry, path: str) -> str:
    return (
        f"https://{config_entry.data['host']}:1234"
        f"/v2/api/site/{config_entry.data['site']}{path}"
    )


def _mock_save(
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    saved: dict[str, Any],
) -> None:
    """Answer the save with the rule, and the refetch after it with the list."""
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        _url(config_entry, f"/qos-rules/{saved['_id']}"),
        json=saved,
        headers={"content-type": "application/json"},
    )
    aioclient_mock.get(
        _url(config_entry, "/qos-rules"),
        json=[saved],
        headers={"content-type": "application/json"},
    )


@pytest.mark.parametrize("qos_rule_payload", [[QOS_RULE]])
async def test_qos_rule_switch(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test a QoS rule is a switch that saves the whole rule."""
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    enabled: dict[str, Any] = {**deepcopy(QOS_RULE), "enabled": True}
    _mock_save(aioclient_mock, config_entry_setup, enabled)

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()

    puts = [call for call in aioclient_mock.mock_calls if call[0].upper() == "PUT"]
    assert len(puts) == 1
    sent = puts[0][2]
    # The controller wants the rule as listed, with only enabled changed
    assert sent == enabled
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    disabled: dict[str, Any] = deepcopy(QOS_RULE)
    _mock_save(aioclient_mock, config_entry_setup, disabled)
    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()

    puts = [call for call in aioclient_mock.mock_calls if call[0].upper() == "PUT"]
    assert puts[0][2]["enabled"] is False
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize("qos_rule_payload", [[QOS_RULE]])
async def test_qos_rule_changed_in_unifi(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test a rule toggled in UniFi shows on the next poll."""
    hub = config_entry_setup.runtime_data

    coordinator = hub.entity_loader.get_data_update_coordinator(qos_rules(hub.api))

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        _url(config_entry_setup, "/qos-rules"),
        json=[{**deepcopy(QOS_RULE), "enabled": True}],
        headers={"content-type": "application/json"},
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_no_qos_rules_endpoint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test an older controller without QoS rules still sets up, without polling them."""
    hub = config_entry_setup.runtime_data

    coordinator = hub.entity_loader.get_data_update_coordinator(qos_rules(hub.api))

    aioclient_mock.clear_requests()
    aioclient_mock.get(_url(config_entry_setup, "/qos-rules"), status=404)
    await coordinator.async_refresh()

    assert coordinator.update_interval is None
    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)
