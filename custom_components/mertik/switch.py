import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory # <--- IMPORT ADDED
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    dev_name = entry.data["name"]
    
    async_add_entities([
        MertikPowerSwitch(dataservice, entry.entry_id, dev_name),
        MertikEcoSwitch(dataservice, entry.entry_id, dev_name),
        MertikAuxSwitch(dataservice, entry.entry_id, dev_name),
        MertikPilotSwitch(dataservice, entry.entry_id, dev_name),
        MertikSmartSyncSwitch(dataservice, entry.entry_id, dev_name),
    ])

# --- CONFIGURATION SWITCH ---
class MertikSmartSyncSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Smart Sync"
        self._attr_unique_id = entry_id + "-smart-sync"
        self._attr_icon = "mdi:sync-alert"
        # FIX: Use the Enum object, not a string
        self._attr_entity_category = EntityCategory.CONFIG 

    async def async_added_to_hass(self):
        """Restore previous setting."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        
        if last_state and last_state.state in ["on", "off"]:
            self._dataservice.smart_sync_enabled = (last_state.state == "on")
        else:
            self._dataservice.smart_sync_enabled = True

    @property
    def is_on(self):
        return getattr(self._dataservice, "smart_sync_enabled", True)

    async def async_turn_on(self, **kwargs):
        self._dataservice.smart_sync_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._dataservice.smart_sync_enabled = False
        self.async_write_ha_state()

# --- BASE SWITCH ---
class MertikBaseSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Base class for Mertik switches with State Restoration."""
    def __init__(self, dataservice, entry_id, name, switch_type):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = f"{name} {switch_type}"
        self._attr_unique_id = f"{entry_id}-{switch_type.lower().replace(' ', '-')}"
        self._was_available = False
        self._is_on_local = False

    @property
    def device_info(self):
        return self._dataservice.device_info

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in ["on", "off"]:
            self._is_on_local = (last_state.state == "on")
        self._was_available = self.coordinator.last_update_success
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        is_available = self.coordinator.last_update_success
        device_is_on = self._get_device_status()
        
        smart_sync = getattr(self._dataservice, "smart_sync_enabled", True)

        # 1. Manual Override
        if self._was_available and is_available:
            self._is_on_local = device_is_on

        # 2. Recovery (Reboot)
        elif not self._was_available and is_available:
            if smart_sync:
                _LOGGER.warning(f"{self.name} recovered. Enforcing HA State: {self._is_on_local}")
            else:
                _LOGGER.info(f"{self.name} recovered. Accepting device state: {device_is_on}")
                self._is_on_local = device_is_on

        self._was_available = is_available
        self.async_write_ha_state()
        
        if smart_sync:
            self.hass.async_create_task(self._sync_hardware())

    async def _sync_hardware(self):
        if not self.coordinator.last_update_success: return
        device_is_on = self._get_device_status()
        
        if self._is_on_local and not device_is_on:
            await self.async_turn_on_device()
        elif not self._is_on_local and device_is_on:
            await self.async_turn_off_device()

    @property
    def is_on(self): return self._is_on_local

    async def async_turn_on(self, **kwargs):
        self._is_on_local = True
        await self.async_turn_on_device()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._is_on_local = False
        await self.async_turn_off_device()
        self.async_write_ha_state()

    def _get_device_status(self): return False
    async def async_turn_on_device(self): pass
    async def async_turn_off_device(self): pass

# --- IMPLEMENTATIONS ---
class MertikPowerSwitch(MertikBaseSwitch):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice, entry_id, name, "Power")
        self._attr_icon = "mdi:fireplace"
    def _get_device_status(self): return self._dataservice.is_on
    async def async_turn_on_device(self): await self._dataservice.async_ignite_fireplace()
    async def async_turn_off_device(self): await self._dataservice.async_guard_flame_off()

class MertikEcoSwitch(MertikBaseSwitch):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice, entry_id, name, "Eco Mode")
        self._attr_icon = "mdi:leaf"
    def _get_device_status(self): return self._dataservice.mertik.mode == "2"
    async def async_turn_on_device(self): await self._dataservice.async_set_eco()
    async def async_turn_off_device(self): await self._dataservice.async_set_manual()

class MertikAuxSwitch(MertikBaseSwitch):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice, entry_id, name, "Secondary Burner")
        self._attr_icon = "mdi:fire"
    def _get_device_status(self): return self._dataservice.is_aux_on
    async def async_turn_on_device(self): await self._dataservice.async_aux_on()
    async def async_turn_off_device(self): await self._dataservice.async_aux_off()

class MertikPilotSwitch(MertikBaseSwitch):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice, entry_id, name, "Keep Pilot On")
        self._attr_icon = "mdi:gas-burner"
    def _get_device_status(self): return getattr(self._dataservice, "keep_pilot_on", False)
    async def async_turn_on_device(self): self._dataservice.keep_pilot_on = True
    async def async_turn_off_device(self):
        self._dataservice.keep_pilot_on = False
        if self._dataservice.is_on and self._dataservice.get_flame_height() == 0:
            await self._dataservice.async_guard_flame_off()
