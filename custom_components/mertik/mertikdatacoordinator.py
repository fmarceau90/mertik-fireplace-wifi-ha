import logging
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
        
        # --- NEW: Memory for the Pilot Switch ---
        # If True, the system will revert to Pilot instead of turning off
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
            
            # Auto-Sync logic: If the fire is OFF physically, 
            # our Pilot Switch memory should probably reset to False
            if not self.mertik.is_on and not self.mertik.is_igniting:
                self.keep_pilot_on = False
                
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
    
    # NEW: Dedicated Pilot Switch Actions
    async def async_toggle_pilot(self, enable: bool):
        self.keep_pilot_on = enable
        if enable:
            # If not already on, ignite. Then set to lowest height (Pilot)
            if not self.mertik.is_on:
                await self.mertik.async_ignite_fireplace()
            await self.mertik.async_set_flame_height(0) # Index 0 = Pilot
        else:
            # Turn OFF completely
            await self.mertik.async_guard_flame_off()
        
        await self.async_request_refresh()

    async def async_ignite_fireplace(self):
        # Called by Thermostat/Main Switch
        await self.mertik.async_ignite_fireplace()
        await self.async_request_refresh()

    async def async_guard_flame_off(self):
        await self.mertik.async_guard_flame_off()
        self.keep_pilot_on = False # Hard Off resets the pilot switch
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
