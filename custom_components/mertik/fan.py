import logging
import math
import asyncio
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
    def device_info(self): return self._dataservice.device_info

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
            if self._is_on_local and not device_is_on: await self._set_fan_hardware()
            elif not self._is_on_local and device_is_on: await self._dataservice.mertik.async_fan_off()
        except Exception as e: _LOGGER.error(f"Error syncing fan hardware: {e}")

    @property
    def is_on(self): return self._is_on_local
    @property
    def percentage(self): return self._percentage_local if self._is_on_local else 0
    @property
    def speed_count(self) -> int: return 4

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        self._is_on_local = True
        if percentage is not None: self._percentage_local = percentage
        elif self._percentage_local is None or self._percentage_local == 0: self._percentage_local = 100
        self.async_write_ha_state()
        await self._set_fan_hardware()

    async def async_turn_off(self, **kwargs):
        self._is_on_local = False
        self.async_write_ha_state()
        try: await self._dataservice.mertik.async_fan_off()
        except Exception as e: _LOGGER.error(f"Failed to turn off fan: {e}")

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
            # Calculate Level 1-4
            if self._percentage_local == 0: 
                level = 0
            else:
                level = int(math.ceil(self._percentage_local / 25))
            
            _LOGGER.info(f"Setting Fan to Level {level}. Initiating 'Kitchen Sink' protocol.")

            # DEBUG: Print attributes to log so we can see the real variable names
            try:
                attrs = dir(self._dataservice.mertik)
                filtered = [a for a in attrs if "fan" in a or "speed" in a]
                _LOGGER.debug(f"[DEBUG INSPECTION] Driver Attributes: {filtered}")
            except:
                pass

            if hasattr(self._dataservice.mertik, "async_set_fan_speed"):
                
                # METHOD 1: VARIABLE INJECTION (Bypass the function)
                # We try to set every common variable name directly
                for var_name in ["_fan_speed", "fan_speed", "_speed", "speed"]:
                    if hasattr(self._dataservice.mertik, var_name):
                        setattr(self._dataservice.mertik, var_name, int(level))
                        _LOGGER.debug(f"Injected {level} into {var_name}")

                # METHOD 2: THE "RISING EDGE" (0 -> Level)
                # Some drivers ignore commands if value == current_value.
                # We force it to 0 first, then to Target.
                await self._dataservice.mertik.async_set_fan_speed(0)
                await asyncio.sleep(0.2) # Tiny pause
                await self._dataservice.mertik.async_set_fan_speed(int(level))
                
                # METHOD 3: FORCE ACTUATION
                # Reset 'On' state so it is forced to send the packet
                self._dataservice.mertik._fan_on = False
                await self._dataservice.mertik.async_fan_on()
                
            else:
                # Fallback
                await self._dataservice.mertik.async_fan_on()
                
        except Exception as e:
            _LOGGER.error(f"Failed to set fan speed: {e}")
