from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    entities = []

    # 1. Main Switch
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

    async_add_entities(entities)


class MertikOnOffSwitchEntity(CoordinatorEntity, SwitchEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name
        self._attr_unique_id = entry_id + "-OnOff"

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def is_on(self):
        """Return true if the device is on."""
        return bool(self._dataservice.is_on)

    async def async_turn_on(self, **kwargs):
        await self._dataservice.async_ignite_fireplace()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.async_guard_flame_off()

    @property
    def icon(self) -> str:
        return "mdi:fireplace"


class MertikAuxOnOffSwitchEntity(CoordinatorEntity, SwitchEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name
        self._attr_unique_id = entry_id + "-AuxOnOff"

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def is_on(self):
        return bool(self._dataservice.is_aux_on)

    async def async_turn_on(self, **kwargs):
        await self._dataservice.async_aux_on()

    async def async_turn_off(self, **kwargs):
        await self._dataservice.async_aux_off()

    @property
    def icon(self) -> str:
        return "mdi:light"


class MertikEcoSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Switch to toggle Eco Wave mode."""
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
        # '2' usually indicates Eco Mode in the Mertik protocol
        return self._dataservice.operating_mode == "2"

    async def async_turn_on(self, **kwargs):
        """Turn Eco Mode on."""
        await self._dataservice.mertik.async_set_eco()
        await self._dataservice.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn Eco Mode off (Return to Manual)."""
        await self._dataservice.mertik.async_set_manual()
        await self._dataservice.async_request_refresh()
