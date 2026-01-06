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
        """Try EVERY method to force the beep."""
        try:
            level_1_to_4 = int(math.ceil(self._percentage_local / 25)) if self._percentage_local > 0 else 0
            raw_percent = int(self._percentage_local)
            
            _LOGGER.info(f"Setting Fan. Level: {level_1_to_4}, Percent: {raw_percent}")

            # 1. FORCED RESET OF 'ON' STATUS
            # This is critical. We force the driver to think it is OFF.
            # This guarantees the next command (On/Set) will generate a Radio Packet.
            if hasattr(self._dataservice.mertik, "_fan_on"):
                self._dataservice.mertik._fan_on = False

            # 2. ATTEMPT A: Set Speed via Method (Try Level first)
            method_called = False
            if hasattr(self._dataservice.mertik, "async_set_fan_speed"):
                try:
                    # Some drivers want 1-4
                    await self._dataservice.mertik.async_set_fan_speed(level_1_to_4)
                    method_called = True
                except:
                    pass
                
                # If that didn't crash, try resetting 'On' flag again and sending percentage
                # (Some drivers want 0-100)
                if hasattr(self._dataservice.mertik, "_fan_on"): self._dataservice.mertik._fan_on = False
                try:
                    await self._dataservice.mertik.async_set_fan_speed(raw_percent)
                    method_called = True
                except:
                    pass

            # 3. ATTEMPT B: Direct Variable Injection
            # If the method failed or doesn't exist, we manually set the internal memory
            if not method_called:
                if hasattr(self._dataservice.mertik, "_fan_speed"):
                    self._dataservice.mertik._fan_speed = level_1_to_4
                
                # 4. FINAL TRIGGER: Force ON
                # Since we set _fan_on to False at the start, this MUST send the packet.
                # And since we injected the speed variable, the packet should contain the new speed.
                await self._dataservice.mertik.async_fan_on()
            
            # 5. Restore Reality
            # We forced it to False to trick it, now we set it back to True locally
            self._is_on_local = True
            if hasattr(self._dataservice.mertik, "_fan_on"):
                 self._dataservice.mertik._fan_on = True

        except Exception as e:
            _LOGGER.error(f"CRITICAL FAILURE in _set_fan_hardware: {e}")
