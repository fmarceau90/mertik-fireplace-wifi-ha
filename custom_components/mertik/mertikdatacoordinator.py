import logging
import asyncio
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class MertikDataCoordinator(DataUpdateCoordinator):
    """Mertik custom coordinator."""

    def __init__(self, hass, mertik, entry_id, device_name):
        super().__init__(
            hass,
            _LOGGER,
            name="Mertik",
            update_interval=timedelta(seconds=15),
        )
        self.mertik = mertik
        self.entry_id = entry_id
        self.device_name = device_name
        self.keep_pilot_on = False 

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry_id)},
            "name": self.device_name,
            "manufacturer": "Mertik Maxitrol",
            "model": "Fireplace WiFi",
        }

    async def _async_update_data(self):
        try:
            await self.mertik.async_refresh_status()

            if self.mertik.is_on and self.mertik.get_flame_height() == 0:
                self.keep_pilot_on = True
            
            return self.mertik
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    # --- Properties ---
    @property
    def is_on(self) -> bool:
        return self.mertik.is_on or self.mertik.is_igniting

    @property
    def operating_mode(self):
        return self.mertik.get_mode

    @property
    def is_aux_on(self) -> bool:
        return self.mertik.is_aux_on

    @property
    def ambient_temperature(self) -> float:
        return self.mertik.ambient_temperature

    @property
    def is_light_on(self) -> bool:
        return self.mertik.is_light_on

    @property
    def light_brightness(self) -> int:
        return self.mertik.light_brightness

    def get_flame_height(self) -> int:
        return self.mertik.get_flame_height()

    # --- Async Actions ---
    
    async def async_toggle_pilot(self, enable: bool):
        self.keep_pilot_on = enable
        
        if enable:
            if not self.mertik.is_on:
                _LOGGER.info("Pilot Switch ON: Sending Ignite Signal.")
                await self.mertik.async_ignite_fireplace()
                
                # Wait 40s to ensure motor is finished moving
                _LOGGER.info("Waiting 40s for hardware ignition cycle...")
                await asyncio.sleep(40)
                
                _LOGGER.info("Dropping flame to Pilot (Level 0).")
                await self.mertik.async_set_flame_height(0)
                
            else:
                _LOGGER.info("Fire is already ON. Updating Pilot Preference to TRUE.")
            
        else:
            if self.mertik.get_flame_height() > 0:
                _LOGGER.info("Fire is HEATING. Updating Pilot Preference to FALSE.")
            else:
                _LOGGER.info("Fire is at PILOT/OFF. Shutting down.")
                await self.mertik.async_guard_flame_off()
        
        await self.async_request_refresh()

    async def async_ignite_fireplace(self):
        await self.mertik.async_ignite_fireplace()

    async def async_guard_flame_off(self):
        await self.mertik.async_guard_flame_off()
        self.keep_pilot_on = False 

    async def async_set_flame_height(self, flame_height) -> None:
        # 1. LOGIC CHECK: If going to Pilot (0), Aux MUST be Off.
        if flame_height == 0 and self.mertik.is_aux_on:
            _LOGGER.info("Flame set to 0 (Pilot). Auto-turning OFF Secondary Burner.")
            self.mertik._aux_on = False # Optimistic update for Aux
            await self.mertik.async_aux_off() # Send command
            # Small pause to let the Aux valve close before moving the Main valve
            await asyncio.sleep(0.5)

        # 2. OPTIMISTIC UPDATE: Update UI immediately
        self.mertik.flameHeight = flame_height
        self.async_update_listeners()
        
        # 3. SEND COMMAND: Move the motor
        await self.mertik.async_set_flame_height(flame_height)
        
        # 4. DO NOT REFRESH. 

    # --- GENTLE MODE COMMANDS (With Optimistic Updates) ---
    
    async def async_aux_on(self):
        self.mertik._aux_on = True 
        self.async_update_listeners()
        await self.mertik.async_aux_on()

    async def async_aux_off(self):
        self.mertik._aux_on = False
        self.async_update_listeners()
        await self.mertik.async_aux_off()

    async def async_light_on(self):
        self.mertik._light_on = True
        self.async_update_listeners()
        await self.mertik.async_light_on()

    async def async_light_off(self):
        self.mertik._light_on = False
        self.async_update_listeners()
        await self.mertik.async_light_off()

    async def async_set_light_brightness(self, brightness) -> None:
        self.mertik._light_brightness = brightness
        self.async_update_listeners()
        await self.mertik.async_set_light_brightness(brightness)
