"""Test that the VLAN option saved by release 2026.10.0-vlan.1 (text) still works."""

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.unifi.const import CONF_VLAN_SENSORS
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_VLAN_SENSORS: "11, 12 ,Native"}]
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_vlan_option_saved_as_text(hass: HomeAssistant) -> None:
    """Verify a text option creates sensors for the listed VLANs only."""
    assert sorted(hass.states.async_entity_ids(SENSOR_DOMAIN)) == [
        "sensor.native_vlan_clients",
        "sensor.native_vlan_traffic",
        "sensor.vlan_11_clients",
        "sensor.vlan_11_traffic",
        "sensor.vlan_12_clients",
        "sensor.vlan_12_traffic",
    ]
