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
        
        # Memory for Pilot Switch: Default False
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

            # --- SYNC LOGIC (UPDATED FOR STABILITY) ---
            # 1. REMOVED "Auto-Off" Logic:
            # We do NOT automatically set keep_pilot_on = False if the fire reports Off.
            # This prevents the switch from turning itself off during connection glitches.
            # The only way to turn it off is for the user to toggle the switch.

            # 2. Auto-Detect Pilot:
            # If the fire IS physically on Pilot, we ensure the variable matches.
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
        """Dedicated Pilot Switch Action with IGNITION DELAY."""
        self.keep_pilot_on = enable
        
        if enable:
            if not self.mertik.is_on:
                _LOGGER.info("Pilot Switch ON: Sending Ignite Signal.")
                await self.mertik.async_ignite_fireplace()
                
                # --- CRITICAL: WAIT FOR IGNITION ---
                # Hardware cannot receive commands while sparking.
                # Wait 25s for main burner to light up before dropping to Pilot.
                _LOGGER.info("Waiting 25s for hardware ignition cycle...")
                await asyncio.sleep(25)
                
            _LOGGER.info("Dropping flame to Pilot (Level 0).")
            await self.mertik.async_set_flame_height(0) 
            
        else:
            # Turn OFF completely
            await self.mertik.async_guard_flame_off()
        
        await self.async_request_refresh()

    async def async_ignite_fireplace(self):
        await self.mertik.async_ignite_fireplace()
        await self.async_request_refresh()

    async def async_guard_flame_off(self):
        await self.mertik.async_guard_flame_off()
        # Only hard shutdown resets the pilot memory
        self.keep_pilot_on = False 
        await self.async_request_refresh()

    async def async_aux_on(self):
        await self.mertik.async_aux_on()
        await self.async_request_refresh()

    async def async_aux_off(self):
        await self.mertik.async_aux_off()
        await self.async_request_refresh()

    async def async_set_flame_height(self, flame_height) -> None:
        await self.mertik.async_set_flame_height(flame_height)
        await self.async_request_refresh()

    async def async_light_on(self):
        await self.mertik.async_light_on()
        await self.async_request_refresh()

    async def async_light_off(self):
        await self.mertik.async_light_off()
        await self.async_request_refresh()

    async def async_set_light_brightness(self, brightness) -> None:
        await self.mertik.async_set_light_brightness(brightness)
        await self.async_request_refresh()
