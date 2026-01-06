import logging
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities([MertikFan(dataservice, entry.entry_id, entry.data["name"])])

class MertikFan(CoordinatorEntity, FanEntity, RestoreEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Fan"
        self._attr_unique_id = entry_id + "-fan"
        # Back to basics: Only On/Off support until we find the speed codes
        self._attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        self._was_available = False
        self._is_on_local = False

    @property
    def device_info(self): return self._dataservice.device_info

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in ["on", "off"]:
            self._is_on_local = (last_state.state == "on")
        self._was_available = self.coordinator.last_update_success
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        is_available = self.coordinator.last_update_success
        device_is_on = getattr(self._dataservice.mertik, "_fan_on", False)
        smart_sync = getattr(self._dataservice, "smart_sync_enabled", True)

        if self._was_available and is_available:
            if self._is_on_local and not device_is_on: pass
            else: self._is_on_local = device_is_on
        elif not self._was_available and is_available:
            if smart_sync:
                _LOGGER.warning(f"Fan recovered. Enforcing HA State: {self._is_on_local}")
            else:
                _LOGGER.info(f"Fan recovered. Smart Sync OFF. Accepting device state: {device_is_on}")
                self._is_on_local = device_is_on
        self._was_available = is_available
        self.async_write_ha_state()
        if smart_sync: self.hass.async_create_task(self._sync_hardware())

    async def _sync_hardware(self):
        if not self.coordinator.last_update_success: return
        device_is_on = getattr(self._dataservice.mertik, "_fan_on", False)
        try:
            if self._is_on_local and not device_is_on: await self._dataservice.mertik.async_fan_on()
            elif not self._is_on_local and device_is_on: await self._dataservice.mertik.async_fan_off()
        except Exception as e: _LOGGER.error(f"Error syncing fan hardware: {e}")

    @property
    def is_on(self): return self._is_on_local

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        self._is_on_local = True
        self.async_write_ha_state()
        await self._dataservice.mertik.async_fan_on()

    async def async_turn_off(self, **kwargs):
        self._is_on_local = False
        self.async_write_ha_state()
        await self._dataservice.mertik.async_fan_off()