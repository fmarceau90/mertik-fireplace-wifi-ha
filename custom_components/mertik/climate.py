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
        
        # Default Settings
        self._target_temp = 21.0
        self._attr_hvac_mode = HVACMode.OFF  # Start as OFF by default
        self._hysteresis = 0.5  # Prevent rapid on/off switching

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def current_temperature(self):
        return self._dataservice.ambient_temperature

    @property
    def hvac_mode(self):
        # Return our internal 'Virtual' mode, not just the flame state
        return self._attr_hvac_mode

    @property
    def hvac_action(self):
        """Return the current running action."""
        if self._attr_hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._dataservice.is_on:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def target_temperature(self):
        return self._target_temp

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        await self._control_heating() # Check logic immediately
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._target_temp = kwargs[ATTR_TEMPERATURE]
            await self._control_heating() # Check logic immediately
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # This runs every time the sensor updates (every 15s)
        self.hass.async_create_task(self._control_heating())
        super()._handle_coordinator_update()

    async def _control_heating(self):
        """The 'Brain': Decide if we need to turn on or off."""
        current_temp = self.current_temperature
        
        # 1. If System is OFF, ensure fire is OFF
        if self._attr_hvac_mode == HVACMode.OFF:
            if self._dataservice.is_on:
                _LOGGER.info("Thermostat set to OFF: Stopping Fire.")
                await self._dataservice.async_guard_flame_off()
            return

        # 2. If System is HEAT, check the temperature
        if self._attr_hvac_mode == HVACMode.HEAT:
            # Too Hot? (Current > Target + Buffer) -> Turn OFF
            if current_temp >= (self._target_temp + self._hysteresis):
                if self._dataservice.is_on:
                    _LOGGER.info(f"reached target {self._target_temp}: Stopping Fire.")
                    await self._dataservice.async_guard_flame_off()
            
            # Too Cold? (Current < Target - Buffer) -> Turn ON
            elif current_temp <= (self._target_temp - self._hysteresis):
                if not self._dataservice.is_on and not self._dataservice.is_igniting:
                    _LOGGER.info(f"Below target {self._target_temp}: Igniting Fire.")
                    await self._dataservice.async_ignite_fireplace()
