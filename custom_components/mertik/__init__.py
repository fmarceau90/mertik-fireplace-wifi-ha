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
    
    # --- SHARED STATE INITIALIZATION ---
    # We initialize these flags here so they exist for all platforms
    coordinator.smart_sync_enabled = True
    coordinator.is_thermostat_active = False  # <--- CRITICAL FIX for Eco Mode

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register the developer service
    async def handle_send_command(call):
        cmd = call.data.get("command")
        coord = hass.data[DOMAIN][entry.entry_id]
        _LOGGER.info(f"Service called: Sending raw command '{cmd}'")
        await coord.mertik._async_send_command(cmd)

    hass.services.async_register(DOMAIN, "send_command", handle_send_command)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
