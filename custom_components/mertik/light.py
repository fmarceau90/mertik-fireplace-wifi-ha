import logging
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities([MertikLight(dataservice, entry.entry_id, entry.data["name"])])

class MertikLight(CoordinatorEntity, LightEntity, RestoreEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Light"
        self._attr_unique_id = entry_id + "-light"
        self._attr_icon = "mdi:lightbulb"
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._was_available = False
        self._is_on_local = False
        self._brightness_local = 255

    @property
    def device_info(self): return self._dataservice.device_info

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._is_on_local = (last_state.state == "on")
            if "brightness" in last_state.attributes:
                self._brightness_local = last_state.attributes["brightness"]
        self._was_available = self.coordinator.last_update_success
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        is_available = self.coordinator.last_update_success
        device_is_on = self._dataservice.is_light_on
        device_brightness = self._dataservice.light_brightness
        smart_sync = getattr(self._dataservice, "smart_sync_enabled", True)

        if self._was_available and is_available:
            self._is_on_local = device_is_on
            if device_is_on: self._brightness_local = device_brightness
        
        elif not self._was_available and is_available:
            if smart_sync:
                _LOGGER.warning(f"Light recovered. Enforcing HA State: {self._is_on_local}")
            else:
                _LOGGER.info(f"Light recovered. Smart Sync OFF. Accepting device state: {device_is_on}")
                self._is_on_local = device_is_on
                if device_is_on: self._brightness_local = device_brightness

        self._was_available = is_available
        self.async_write_ha_state()
        
        if smart_sync:
            self.hass.async_create_task(self._sync_hardware())

    async def _sync_hardware(self):
        if not self.coordinator.last_update_success: return
        device_is_on = self._dataservice.is_light_on
        if self._is_on_local and not device_is_on:
            await self._dataservice.async_set_light_brightness(self._brightness_local)
        elif not self._is_on_local and device_is_on:
            await self._dataservice.async_light_off()

    @property
    def is_on(self): return self._is_on_local
    @property
    def brightness(self): return self._brightness_local

    async def async_turn_on(self, **kwargs):
        self._is_on_local = True
        if "brightness" in kwargs: self._brightness_local = kwargs["brightness"]
        await self._dataservice.async_set_light_brightness(self._brightness_local)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._is_on_local = False
        await self._dataservice.async_light_off()
        self.async_write_ha_state()
