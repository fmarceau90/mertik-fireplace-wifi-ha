import logging
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities([MertikLight(dataservice, entry.entry_id, entry.data["name"])])

class MertikLight(CoordinatorEntity, LightEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Light"
        self._attr_unique_id = entry_id + "-light"
        self._attr_icon = "mdi:lightbulb"
        # We support Dimming (Brightness)
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def is_on(self):
        return self._dataservice.is_light_on

    @property
    def brightness(self):
        return self._dataservice.light_brightness

    async def async_turn_on(self, **kwargs):
        # Check if user set a specific brightness slider value
        if "brightness" in kwargs:
            brightness = kwargs["brightness"]
            await self._dataservice.async_set_light_brightness(brightness)
        else:
            # Just toggle ON (restores previous brightness usually)
            await self._dataservice.async_light_on()
        
        # Optimistic update for UI responsiveness
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.async_light_off()
        self.async_write_ha_state()

    @property
    def device_info(self):
        return self._dataservice.device_info
