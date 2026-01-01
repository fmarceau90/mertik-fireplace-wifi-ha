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
        self._hysteresis = 0.5 # Used for shutdown threshold only now

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
            
            # AUTO-ON LOGIC
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
        """The Smart Proportional Logic."""
        
        if not self.coordinator.last_update_success:
            return

        # 1. Manual Mode Check (If OFF, do nothing)
        if self._attr_hvac_mode == HVACMode.OFF:
            return 

        current_temp = self.current_temperature
        
        # 2. HEAT MODE LOGIC
        if self._attr_hvac_mode == HVACMode.HEAT:
            
            # Calculate the Gap (Error)
            delta = self._target_temp - current_temp
            
            # --- SCENARIO A: TOO HOT (Shutdown) ---
            # If we are hotter than target + hysteresis (0.5), shut down.
            if delta <= -0.5:
                if self._dataservice.is_on and self._dataservice.get_flame_height() > 0:
                    _LOGGER.info("Thermostat: Target reached (Overheated).")
                    if self._dataservice.keep_pilot_on:
                        await self._dataservice.async_set_flame_height(0)
                    else:
                        await self._dataservice.async_guard_flame_off()
            
            # --- SCENARIO B: HEATING NEEDED ---
            elif delta > 0:
                
                # Step 1: Ignite if completely dead
                if not self._dataservice.is_on:
                    _LOGGER.info("Thermostat: Too cold. Igniting.")
                    await self._dataservice.async_ignite_fireplace()
                    return # Wait for next cycle to set height
                
                # Step 2: Calculate Proportional Flame Height
                # Logic: 2.0 degrees difference = Max Flame (12)
                # Ratio = 6 steps per 1 degree C.
                
                target_height = int(delta * 6)
                
                # Clamp boundaries (Min 1, Max 12)
                if target_height > 12: target_height = 12
                if target_height < 1: target_height = 1 # Keep a small flame if delta is tiny (e.g. 0.1)
                
                current_height = self._dataservice.get_flame_height()
                
                # Step 3: Apply Change (Only if different)
                if current_height != target_height:
                    _LOGGER.info(f"Thermostat: Proportional Adjust. Delta={delta:.1f}°C -> Flame {target_height}")
                    await self._dataservice.async_set_flame_height(target_height)
                
                # (Optional) If we are sitting at Pilot (0) and need heat, the logic above 
                # naturally handles it: 0 != target_height, so it ramps up immediately.
