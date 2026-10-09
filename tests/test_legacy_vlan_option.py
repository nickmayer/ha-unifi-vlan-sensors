"""Test that the VLAN option saved by release 2026.10.0-vlan.1 (text) still works."""

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.unifi.const import CONF_MORE_OPTIONS, CONF_VLAN_SENSORS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_VLAN_SENSORS: "11, 12 ,Native"}]
)
async def test_options_form_with_text_option(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Verify the options form offers the listed VLANs, not their characters."""
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
    assert [option["value"] for option in vlan_selector.config["options"]] == [
        "11",
        "12",
        "native",
    ]
