"""Tests of the VLAN leases sensor."""

from typing import Any

import pytest

from homeassistant.components.unifi.const import CONF_VLAN_SENSORS
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

NOAH = {
    "_id": "id-noah",
    "name": "noah_vlan11",
    "purpose": "corporate",
    "enabled": True,
    "vlan_enabled": True,
    "vlan": 11,
}


def _overview(leases: int) -> list[dict[str, Any]]:
    return [
        {
            "configuration": NOAH,
            "statistics": {"dhcp_active_leases": leases, "dhcp_max_leases": 249},
        }
    ]


@pytest.mark.parametrize("config_entry_options", [{CONF_VLAN_SENSORS: ["11", "12"]}])
@pytest.mark.parametrize("network_payload", [[NOAH]])
@pytest.mark.parametrize("lan_overview_payload", [_overview(3)])
@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "mac": "00:00:00:00:00:01",
                "name": "Online",
                "vlan": 11,
                "is_wired": False,
                "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
            }
        ]
    ],
)
async def test_vlan_leases_sensor(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test the active leases are the state, with the online clients as attribute."""
    await async_update_entity(hass, "sensor.noah_vlan11_leases")
    state = hass.states.get("sensor.noah_vlan11_leases")

    assert state.state == "3"
    assert state.attributes["online"] == 1
    assert state.attributes["max_leases"] == 249

    # A VLAN without a network, or without lease data from the controller
    await async_update_entity(hass, "sensor.vlan_12_leases")
    assert hass.states.get("sensor.vlan_12_leases").state == STATE_UNKNOWN
