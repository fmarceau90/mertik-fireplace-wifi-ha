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
        # If fire is active and ABOVE Pilot level, we are Heating
        # If fire is just at Pilot (Index 0), we are technically 'Idle'
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
        await self._control_heating()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            self._target_temp = kwargs[ATTR_TEMPERATURE]
            await self._control_heating()
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._control_heating())
        super()._handle_coordinator_update()

    async def _control_heating(self):
        """The Smart Logic with Pilot Support."""
        current_temp = self.current_temperature
        
        # 1. System Set to OFF
        if self._attr_hvac_mode == HVACMode.OFF:
            # If User wants Pilot, drop to Pilot. Else, Shutdown.
            if self._dataservice.is_on:
                if self._dataservice.keep_pilot_on:
                     if self._dataservice.get_flame_height() > 0:
                         await self._dataservice.async_set_flame_height(0)
                else:
                     await self._dataservice.async_guard_flame_off()
            return

        # 2. System Set to HEAT
        if self._attr_hvac_mode == HVACMode.HEAT:
            # TOO HOT -> Stop Heating (Drop to Pilot OR Shutdown)
            if current_temp >= (self._target_temp + self._hysteresis):
                if self._dataservice.is_on and self._dataservice.get_flame_height() > 0:
                    _LOGGER.info("Target reached.")
                    
                    if self._dataservice.keep_pilot_on:
                        _LOGGER.info("Dropping to Pilot (Switch is ON).")
                        await self._dataservice.async_set_flame_height(0)
                    else:
                        _LOGGER.info("Shutting down (Switch is OFF).")
                        await self._dataservice.async_guard_flame_off()

            # TOO COLD -> Start Heating
            elif current_temp <= (self._target_temp - self._hysteresis):
                # If we are Off OR just in Pilot mode -> Boost it!
                if not self._dataservice.is_on or self._dataservice.get_flame_height() == 0:
                    _LOGGER.info("Too cold. Boosting flame.")
                    # Ignite / Set to a decent starting height (e.g. Index 1 or higher)
                    # For Mertik, ignite usually goes to High or Last? 
                    # Let's just Ignite (defaults) or Set to Max? 
                    # Usually ignite is enough to start the cycle.
                    await self._dataservice.async_ignite_fireplace()
