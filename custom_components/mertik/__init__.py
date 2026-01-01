import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .mertik import Mertik
from .mertikdatacoordinator import MertikDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "number", "switch", "fan", "binary_sensor", "light", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mertik from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    device_ip = entry.data["host"]
    mertik_device = Mertik(device_ip)

    coordinator = MertikDataCoordinator(
        hass, 
        mertik_device, 
        entry.entry_id, 
        entry.data["name"]
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok