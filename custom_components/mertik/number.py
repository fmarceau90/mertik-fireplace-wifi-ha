import logging
from homeassistant.components.number import NumberEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities([MertikFlameHeight(dataservice, entry.entry_id, entry.data["name"])])

class MertikFlameHeight(NumberEntity):
    """The Flame Height Slider (0-12)."""
    
    def __init__(self, dataservice, entry_id, name):
        self._dataservice = dataservice
        self._attr_name = name + " Flame Height"
        self._attr_unique_id = entry_id + "-FlameHeight"
        self._attr_icon = "mdi:fire"
        
        # KEY CHANGE: Allow 0.
        # 0 = Pilot Only (Standby)
        # 1 = Minimum Main Flame
        # 12 = Maximum Main Flame
        self._attr_native_min_value = 0
        self._attr_native_max_value = 12
        self._attr_native_step = 1

    @property
    def native_value(self):
        """Return the current flame height."""
        return self._dataservice.get_flame_height()

    async def async_set_native_value(self, value: float) -> None:
        """Update the flame height."""
        target_step = int(value)
        
        # If user drags to 0, we send the Standby/Pilot command
        _LOGGER.info(f"Manually setting flame height to {target_step}")
        await self._dataservice.async_set_flame_height(target_step)

    @property
    def device_info(self):
        return self._dataservice.device_info
    
    # Optional: Update the entity when the coordinator updates
    async def async_added_to_hass(self):
        self.async_on_remove(
            self._dataservice.async_add_listener(self.async_write_ha_state)
        )
