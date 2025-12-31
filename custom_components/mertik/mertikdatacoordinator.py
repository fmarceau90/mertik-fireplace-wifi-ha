import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class MertikDataCoordinator(DataUpdateCoordinator):
    """Mertik custom coordinator."""

    def __init__(self, hass, mertik):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Mertik",
            update_interval=timedelta(seconds=15),
        )
        self.mertik = mertik

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            # Calls the new Async method in mertik.py
            await self.mertik.async_refresh_status()
            return self.mertik
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    # --- Properties (Read from internal state) ---
    @property
    def is_on(self) -> bool:
        return self.mertik.is_on or self.mertik.is_igniting

    @property
    def operating_mode(self):
        # Exposes the raw mode byte you wanted to keep
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

    # --- Async Actions (Write to device) ---
    async def async_ignite_fireplace(self):
        await self.mertik.async_ignite_fireplace()
        await self.async_request_refresh()

    async def async_guard_flame_off(self):
        await self.mertik.async_guard_flame_off()
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
