import logging
import math
import asyncio # <--- REQUIRED for the delay
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
        
        # 1 = Set Speed/Percentage feature
        self._attr_supported_features = (
            FanEntityFeature.TURN_ON 
            | FanEntityFeature.TURN_OFF 
            | 1 
        )
        
        self._was_available = False
        self._is_on_local = False
        self._percentage_local = 100

    @property
    def device_info(self):
        return self._dataservice.device_info

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        
        if last_state and last_state.state in ["on", "off"]:
            self._is_on_local = (last_state.state == "on")
        
        if last_state and "percentage" in last_state.attributes:
             stored_p = last_state.attributes["percentage"]
             if stored_p is not None:
                 self._percentage_local = stored_p

        self._was_available = self.coordinator.last_update_success
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        is_available = self.coordinator.last_update_success
        device_is_on = getattr(self._dataservice.mertik, "_fan_on", False)
        smart_sync = getattr(self._dataservice, "smart_sync_enabled", True)

        if self._was_available and is_available:
            # Optimistic Logic: Trust local "On" even if device reports "Off" (Cold Sensor)
            if self._is_on_local and not device_is_on:
                 pass 
            else:
                 self._is_on_local = device_is_on

        elif not self._was_available and is_available:
            if smart_sync:
                _LOGGER.warning(f"Fan recovered. Enforcing HA State: {self._is_on_local}")
            else:
                _LOGGER.info(f"Fan recovered. Smart Sync OFF. Accepting device state: {device_is_on}")
                self._is_on_local = device_is_on

        self._was_available = is_available
        self.async_write_ha_state()
        
        if smart_sync:
            self.hass.async_create_task(self._sync_hardware())

    async def _sync_hardware(self):
        if not self.coordinator.last_update_success: return
        device_is_on = getattr(self._dataservice.mertik, "_fan_on", False)
        
        try:
            if self._is_on_local and not device_is_on:
                await self._set_fan_hardware()
            elif not self._is_on_local and device_is_on:
                await self._dataservice.mertik.async_fan_off()
        except Exception as e:
            _LOGGER.error(f"Error syncing fan hardware: {e}")

    @property
    def is_on(self):
        return self._is_on_local

    @property
    def percentage(self):
        return self._percentage_local if self._is_on_local else 0

    @property
    def speed_count(self) -> int:
        return 4

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        self._is_on_local = True
        
        if percentage is not None:
            self._percentage_local = percentage
        elif self._percentage_local is None or self._percentage_local == 0:
            self._percentage_local = 100

        self.async_write_ha_state()
        await self._set_fan_hardware()

    async def async_turn_off(self, **kwargs):
        self._is_on_local = False
        self.async_write_ha_state()
        try:
            await self._dataservice.mertik.async_fan_off()
        except Exception as e:
            _LOGGER.error(f"Failed to turn off fan: {e}")

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
            
        self._is_on_local = True
        self._percentage_local = percentage
        self.async_write_ha_state()
        await self._set_fan_hardware()

    async def _set_fan_hardware(self):
        try:
            if self._percentage_local == 0:
                level = 0
            else:
                level = int(math.ceil(self._percentage_local / 25))
            
            _LOGGER.debug(f"Setting Fan to Level {level} ({self._percentage_local}%)")
            
            if hasattr(self._dataservice.mertik, "async_set_fan_speed"):
                # 1. Update the Speed Register
                await self._dataservice.mertik.async_set_fan_speed(int(level))
                
                # 2. THE HUMAN BLINK (Force Actuation)
                # We turn it off, wait for the receiver to process "OFF", then turn ON.
                await self._dataservice.mertik.async_fan_off()
                
                # Wait 0.5s for RF transmission clearance
                await asyncio.sleep(0.5)
                
                await self._dataservice.mertik.async_fan_on()
            else:
                await self._dataservice.mertik.async_fan_on()
                
        except Exception as e:
            _LOGGER.error(f"Failed to set fan speed: {e}")
