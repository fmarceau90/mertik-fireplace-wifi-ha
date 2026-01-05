import logging
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities([MertikClimate(dataservice, entry.entry_id, entry.data["name"])])

class MertikClimate(CoordinatorEntity, ClimateEntity, RestoreEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Thermostat"
        self._attr_unique_id = entry_id + "-Climate"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        
        self._target_temp = 21.0
        self._attr_hvac_mode = HVACMode.OFF 
        self._was_available = False
        self._was_on = False

    @property
    def device_info(self): return self._dataservice.device_info

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            if last_state.state in [HVACMode.HEAT, HVACMode.OFF]:
                self._attr_hvac_mode = last_state.state
            if ATTR_TEMPERATURE in last_state.attributes:
                try:
                    self._target_temp = float(last_state.attributes[ATTR_TEMPERATURE])
                except (ValueError, TypeError):
                    self._target_temp = 21.0
        self._was_available = self.coordinator.last_update_success
        self._was_on = self._dataservice.is_on
        self._update_lock_status()

    def _update_lock_status(self):
        is_active = (self._attr_hvac_mode == HVACMode.HEAT)
        self._dataservice.is_thermostat_active = is_active

    @property
    def current_temperature(self): return self._dataservice.ambient_temperature
    @property
    def hvac_mode(self): return self._attr_hvac_mode
    @property
    def hvac_action(self):
        if self._attr_hvac_mode == HVACMode.OFF: return HVACAction.OFF
        if self._dataservice.is_on:
             return HVACAction.HEATING if self._dataservice.get_flame_height() > 0 else HVACAction.IDLE
        return HVACAction.IDLE
    @property
    def target_temperature(self): return self._target_temp

    async def async_set_hvac_mode(self, hvac_mode):
        self._attr_hvac_mode = hvac_mode
        self._update_lock_status()
        if hvac_mode == HVACMode.OFF:
            if self._dataservice.keep_pilot_on:
                 if self._dataservice.get_flame_height() > 0:
                     await self._dataservice.async_set_flame_height(0)
            else:
                 await self._dataservice.async_guard_flame_off()
        elif hvac_mode == HVACMode.HEAT:
            await self._control_heating()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            self._target_temp = kwargs[ATTR_TEMPERATURE]
            if self._attr_hvac_mode == HVACMode.HEAT:
                await self._control_heating()
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        is_available = self.coordinator.last_update_success
        is_on = self._dataservice.is_on
        
        # Check Config
        smart_sync = getattr(self._dataservice, "smart_sync_enabled", True)

        # 1. Manual Sync
        if self._was_available and is_available:
            if self._was_on != is_on:
                if is_on: 
                    if self._attr_hvac_mode == HVACMode.OFF:
                        self._attr_hvac_mode = HVACMode.HEAT
                else: 
                    if self._attr_hvac_mode == HVACMode.HEAT:
                        self._attr_hvac_mode = HVACMode.OFF
        
        # 2. Recovery Sync
        elif not self._was_available and is_available:
            if smart_sync:
                _LOGGER.warning("Device recovered. Enforcing HA State (Smart Sync ON).")
                # Do nothing -> Keeps HA state -> Control Loop enforces it
            else:
                _LOGGER.info("Device recovered. Accepting device state (Smart Sync OFF).")
                # Update HA to match device
                if is_on: self._attr_hvac_mode = HVACMode.HEAT
                else: self._attr_hvac_mode = HVACMode.OFF

        self._was_available = is_available
        self._was_on = is_on
        self._update_lock_status()
        self.hass.async_create_task(self._control_heating())
        super()._handle_coordinator_update()

    async def _control_heating(self):
        if not self.coordinator.last_update_success: return
        if self._attr_hvac_mode == HVACMode.OFF: return 
        
        current_temp = self.current_temperature
        delta = self._target_temp - current_temp
        hysteresis = self._dataservice.thermostat_deadzone
        
        if self._attr_hvac_mode == HVACMode.HEAT:
            if delta <= 0:
                if self._dataservice.get_flame_height() > 0:
                    if self._dataservice.keep_pilot_on:
                        await self._dataservice.async_set_flame_height(0)
                    else:
                        if delta <= -0.5 and not self._dataservice.keep_pilot_on:
                             await self._dataservice.async_guard_flame_off()
                        else:
                             await self._dataservice.async_set_flame_height(0)
            elif delta > hysteresis:
                if not self._dataservice.is_on:
                    await self._dataservice.async_ignite_fireplace()
                    return 
                
                raw_height = int(delta * 6)
                target_height = max(1, min(12, raw_height))
                current_height = self._dataservice.get_flame_height()
                if current_height != target_height:
                    await self._dataservice.async_set_flame_height(target_height)
