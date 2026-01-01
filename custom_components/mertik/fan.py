import logging
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities([MertikFan(dataservice, entry.entry_id, entry.data["name"])])

class MertikFan(CoordinatorEntity, FanEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Fan"
        self._attr_unique_id = entry_id + "-fan"
        self._attr_icon = "mdi:fan"
        # We only support simple On/Off for now
        self._attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    @property
    def is_on(self):
        return self._dataservice.mertik._fan_on

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        # Sending standard ON command
        await self._dataservice.mertik.async_fan_on()
        # Optimistic update
        self._dataservice.mertik._fan_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.mertik.async_fan_off()
        # Optimistic update
        self._dataservice.mertik._fan_on = False
        self.async_write_ha_state()

    @property
    def device_info(self):
        return self._dataservice.device_info
