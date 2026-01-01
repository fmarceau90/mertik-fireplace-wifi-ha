from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.number import NumberEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    entities = []
    entities.append(
        MertikFlameHeightEntity(hass, dataservice, entry.entry_id, entry.data["name"])
    )
    async_add_entities(entities)

class MertikFlameHeightEntity(CoordinatorEntity, NumberEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Flame Height"
        self._attr_unique_id = entry_id + "-FlameHeight"
        
        # UI 1 = Index 0 (Pilot)
        self._attr_native_min_value = 1
        # Array in mertik.py has 13 steps (0 to 12). 
        # So UI max is 13 (Index 12).
        self._attr_native_max_value = 13 
        self._attr_native_step = 1

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def native_value(self) -> float:
        # Convert internal index (0-based) to UI value (1-based)
        return self._dataservice.get_flame_height() + 1

    async def async_set_native_value(self, value: float) -> None:
        # Convert UI value (1-based) to internal index (0-based)
        index = int(value) - 1
        await self._dataservice.async_set_flame_height(index)

    @property
    def icon(self) -> str:
        return "mdi:fire"
