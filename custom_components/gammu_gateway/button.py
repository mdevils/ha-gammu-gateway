"""Button platform for the SMS Gammu Gateway integration."""
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_HOST

from .const import DATA_ENTRIES, DOMAIN
from .coordinator import GammuGatewayCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the modem reset button."""
    coordinator: GammuGatewayCoordinator = hass.data[DOMAIN][DATA_ENTRIES][
        entry.entry_id
    ]
    host = entry.data[CONF_HOST]
    async_add_entities([GammuResetButton(coordinator, entry.entry_id, host)])


class GammuResetButton(ButtonEntity):
    """Button that resets the modem."""

    def __init__(self, coordinator: GammuGatewayCoordinator, entry_id, host):
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._host = host
        self._attr_translation_key = "reset_modem"
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry_id}_reset_button"
        self._attr_icon = "mdi:restart"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"Gammu Gateway ({self._host})",
            "manufacturer": "Gammu",
            "model": "SMS Gateway",
            "configuration_url": f"http://{self._host}:5000",
        }

    async def async_press(self):
        await self._coordinator.client.reset_modem()
