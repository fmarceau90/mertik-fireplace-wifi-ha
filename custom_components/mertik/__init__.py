import logging
from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST
from .mertik import Mertik
from .mertikdatacoordinator import MertikDataCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Load all platforms at once
PLATFORMS = ["switch", "number", "light", "sensor"]

async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up the Mertik component."""
    
    # 1. Get Host
    host = entry.data.get(CONF_HOST)
    if not host:
        return False
        
    # 2. Init API and Coordinator
    mertik = Mertik(host)
    coordinator = MertikDataCoordinator(hass, mertik)

    # 3. First Refresh (Get initial data)
    await coordinator.async_config_entry_first_refresh()

    # 4. Store
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 5. Load Platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
