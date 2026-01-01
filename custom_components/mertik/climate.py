import logging
from homeassistant.components.climate import (
    ClimateEntity, 
    ClimateEntityFeature, 
    HVACMode, 
    HVACAction
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities([MertikClimate(dataservice, entry.entry_id, entry.data["name"])])

class MertikClimate(CoordinatorEntity, ClimateEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name
        self._attr_unique_id = entry_id + "-Climate"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        
        self._target_temp = 21.0
        self._attr_hvac_mode = HVACMode.OFF 
        self._hysteresis = 0.5

    @property
    def device_info(self):
        return self._dataservice.device_info

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
        """Handle User switching the Mode."""
        self._attr_hvac_mode = hvac_mode
        
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
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._target_temp = kwargs[ATTR_TEMPERATURE]
            
            # --- NEW: AUTO-ON LOGIC ---
            # If User raises the temp above current room temp, 
            # we assume they want HEAT, even if it was OFF.
            if self._attr_hvac_mode == HVACMode.OFF:
                if self._target_temp > (self.current_temperature + self._hysteresis):
                    _LOGGER.info("User raised target temp. Auto-switching to HEAT mode.")
                    self._attr_hvac_mode = HVACMode.HEAT

            await self._control_heating()
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._control_heating())
        super()._handle_coordinator_update()

    async def _control_heating(self):
        """The Smart Logic."""
        
        if not self.coordinator.last_update_success:
            return

        # Manual Mode Check
        if self._attr_hvac_mode == HVACMode.OFF:
            return 

        current_temp = self.current_temperature
        
        if self._attr_hvac_mode == HVACMode.HEAT:
            # TOO HOT -> Stop Heating
            if current_temp >= (self._target_temp + self._hysteresis):
                if self._dataservice.is_on and self._dataservice.get_flame_height() > 0:
                    _LOGGER.info("Thermostat: Target reached.")
                    if self._dataservice.keep_pilot_on:
                        await self._dataservice.async_set_flame_height(0)
                    else:
                        await self._dataservice.async_guard_flame_off()

            # TOO COLD -> Start Heating
            elif current_temp <= (self._target_temp - self._hysteresis):
                if not self._dataservice.is_on or self._dataservice.get_flame_height() == 0:
                    _LOGGER.info("Thermostat: Too cold. Boosting flame.")
                    await self._dataservice.async_ignite_fireplace()
