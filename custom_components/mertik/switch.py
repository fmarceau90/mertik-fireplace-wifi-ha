import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    device_name = entry.data["name"]
    
    async_add_entities([
        MertikMainSwitch(dataservice, entry.entry_id, device_name),
        MertikAuxSwitch(dataservice, entry.entry_id, device_name),
        MertikPilotSwitch(dataservice, entry.entry_id, device_name),
        MertikEcoSwitch(dataservice, entry.entry_id, device_name),
    ])

# --- 1. MASTER POWER SWITCH ---
class MertikMainSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        # FRIENDLY NAME: "Fireplace Power"
        self._attr_name = name + " Power"
        self._attr_unique_id = entry_id + "-main"
        self._attr_icon = "mdi:fireplace"

    @property
    def is_on(self):
        # It is "On" if there is any fire (Main or Pilot)
        return self._dataservice.is_on

    async def async_turn_on(self, **kwargs):
        # Ignite to Auto (Standard start)
        await self._dataservice.async_ignite_fireplace()

    async def async_turn_off(self, **kwargs):
        # Full Shutdown
        await self._dataservice.async_guard_flame_off()
        
    @property
    def device_info(self):
        return self._dataservice.device_info


# --- 2. SECONDARY BURNER (AUX) ---
class MertikAuxSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        # FRIENDLY NAME: "Secondary Burner"
        self._attr_name = name + " Secondary Burner"
        self._attr_unique_id = entry_id + "-aux"
        self._attr_icon = "mdi:fire-alert"

    @property
    def is_on(self):
        return self._dataservice.is_aux_on

    async def async_turn_on(self, **kwargs):
        await self._dataservice.async_aux_on()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.async_aux_off()
        
    @property
    def device_info(self):
        return self._dataservice.device_info


# --- 3. PILOT PREFERENCE SWITCH ---
class MertikPilotSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        # FRIENDLY NAME: "Keep Pilot On"
        self._attr_name = name + " Keep Pilot On"
        self._attr_unique_id = entry_id + "-pilot"
        self._attr_icon = "mdi:gas-burner"

    @property
    def is_on(self):
        return self._dataservice.keep_pilot_on

    async def async_turn_on(self, **kwargs):
        await self._dataservice.async_toggle_pilot(True)

    async def async_turn_off(self, **kwargs):
        await self._dataservice.async_toggle_pilot(False)

    @property
    def device_info(self):
        return self._dataservice.device_info


# --- 4. ECO MODE SWITCH ---
class MertikEcoSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Eco Mode"
        self._attr_unique_id = entry_id + "-eco"
        self._attr_icon = "mdi:leaf"

    @property
    def is_on(self):
        return self._dataservice.operating_mode == "2"

    async def async_turn_on(self, **kwargs):
        await self._dataservice.mertik.async_set_eco()
        await self._dataservice.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.mertik.async_set_manual()
        await self._dataservice.async_request_refresh()

    @property
    def device_info(self):
        return self._dataservice.device_info
