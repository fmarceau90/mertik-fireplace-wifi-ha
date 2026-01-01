from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    entities = []

    # 1. Main Switch (Controls Ignition/Shutdown)
    entities.append(
        MertikOnOffSwitchEntity(hass, dataservice, entry.entry_id, entry.data["name"])
    )

    # 2. Aux Switch
    entities.append(
        MertikAuxOnOffSwitchEntity(
            hass, dataservice, entry.entry_id, entry.data["name"] + " Aux"
        )
    )

    # 3. Eco Mode Switch
    entities.append(
        MertikEcoSwitchEntity(
            hass, dataservice, entry.entry_id, entry.data["name"] + " Eco Mode"
        )
    )
    
    # 4. NEW: Pilot / Guide Switch
    entities.append(
        MertikPilotSwitchEntity(
            hass, dataservice, entry.entry_id, entry.data["name"] + " Pilot"
        )
    )

    async_add_entities(entities)


class MertikOnOffSwitchEntity(CoordinatorEntity, SwitchEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name
        self._attr_unique_id = entry_id + "-OnOff"
        self._attr_icon = "mdi:fireplace"

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def is_on(self):
        return bool(self._dataservice.is_on)

    async def async_turn_on(self, **kwargs):
        await self._dataservice.async_ignite_fireplace()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.async_guard_flame_off()


class MertikPilotSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Specific Switch for the Pilot / Guide Flame."""
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name
        self._attr_unique_id = entry_id + "-Pilot"
        self._attr_icon = "mdi:fire-alert" # Icon for pilot light

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def is_on(self):
        # It's ON if the user wanted it ON, AND the fire is physically present
        return self._dataservice.keep_pilot_on and self._dataservice.is_on

    async def async_turn_on(self, **kwargs):
        """Turn on Pilot Mode."""
        await self._dataservice.async_toggle_pilot(True)

    async def async_turn_off(self, **kwargs):
        """Turn off Pilot Mode (Shutdown)."""
        await self._dataservice.async_toggle_pilot(False)


class MertikAuxOnOffSwitchEntity(CoordinatorEntity, SwitchEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name
        self._attr_unique_id = entry_id + "-AuxOnOff"
        self._attr_icon = "mdi:light"

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def is_on(self):
        return bool(self._dataservice.is_aux_on)

    async def async_turn_on(self, **kwargs):
        await self._dataservice.async_turn_on() # Fix: Should be async_aux_on

    async def async_turn_off(self, **kwargs):
        await self._dataservice.async_aux_off()


class MertikEcoSwitchEntity(CoordinatorEntity, SwitchEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name
        self._attr_unique_id = entry_id + "-EcoMode"
        self._attr_icon = "mdi:leaf"

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def is_on(self):
        return self._dataservice.operating_mode == "2"

    async def async_turn_on(self, **kwargs):
        await self._dataservice.mertik.async_set_eco()
        await self._dataservice.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.mertik.async_set_manual()
        await self._dataservice.async_request_refresh()
