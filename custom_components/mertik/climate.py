import logging
from homeassistant.components.climate import (
    ClimateEntity, 
    ClimateEntityFeature, 
    HVACMode, 
    HVACAction
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
        
        # Defaults
        self._target_temp = 21.0
        self._attr_hvac_mode = HVACMode.OFF 
        
        # HYSTERESIS SETTINGS
        self._hysteresis_start = 0.5 

    @property
    def device_info(self):
        return self._dataservice.device_info

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        
        # Restore State
        last_state = await self.async_get_last_state()
        if last_state:
            _LOGGER.info(f"Restoring thermostat state: {last_state.state}")
            
            if last_state.state in [HVACMode.HEAT, HVACMode.OFF]:
                self._attr_hvac_mode = last_state.state
            
            if ATTR_TEMPERATURE in last_state.attributes:
                try:
                    self._target_temp = float(last_state.attributes[ATTR_TEMPERATURE])
                except (ValueError, TypeError):
                    self._target_temp = 21.0

        self._update_lock_status()

    def _update_lock_status(self):
        """Tell the coordinator if we are active."""
        is_active = (self._attr_hvac_mode == HVACMode.HEAT)
        self._dataservice.is_thermostat_active = is_active

    @property
    def current_temperature(self):
        return self._dataservice.ambient_temperature

    @property
    def hvac_mode(self):
        return self._attr_hvac_mode

    @property
    def hvac_action(self):
        if self._attr_hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._dataservice.is_on:
             if self._dataservice.get_flame_height() > 0:
                 return HVACAction.HEATING
             else:
                 return HVACAction.IDLE
        return HVACAction.IDLE

    @property
    def target_temperature(self):
        return self._target_temp

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
            
            if self._attr_hvac_mode == HVACMode.OFF:
                if self._target_temp > (self.current_temperature + self._hysteresis_start):
                    self._attr_hvac_mode = HVACMode.HEAT
                    self._update_lock_status()

            await self._control_heating()
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._control_heating())
        super()._handle_coordinator_update()

    async def _control_heating(self):
        if not self.coordinator.last_update_success:
            return

        if self._attr_hvac_mode == HVACMode.OFF:
            return 

        current_temp = self.current_temperature
        delta = self._target_temp - current_temp
        
        if self._attr_hvac_mode == HVACMode.HEAT:
            
            # 1. TARGET REACHED (Stop Heating)
            if delta <= 0:
                if self._dataservice.get_flame_height() > 0:
                    if self._dataservice.keep_pilot_on:
                        await self._dataservice.async_set_flame_height(0)
                    else:
                        if delta <= -0.5 and not self._dataservice.keep_pilot_on:
                             await self._dataservice.async_guard_flame_off()
                        else:
                             await self._dataservice.async_set_flame_height(0)

            # 2. START HEATING (Start Heating)
            elif delta > self._hysteresis_start:
                
                if not self._dataservice.is_on:
                    await self._dataservice.async_ignite_fireplace()
                    return 
                
                # Proportional Heating Calculation
                raw_height = int(delta * 6)
                
                # --- THE CLAMP FIX ---
                # Ensure we never ask for more than 12 or less than 1
                target_height = max(1, min(12, raw_height))
                
                current_height = self._dataservice.get_flame_height()
                if current_height != target_height:
                    _LOGGER.info(f"Heating required (Delta {delta:.1f}). Setting flame to {target_height}.")
                    await self._dataservice.async_set_flame_height(target_height)
