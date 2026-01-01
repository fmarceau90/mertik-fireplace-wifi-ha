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
        
        # UI Range: 1 (Low Burner) to 12 (High Burner)
        # We REMOVED Pilot (Index 0) from the valid set options
        self._attr_native_min_value = 1
        self._attr_native_max_value = 12 
        self._attr_native_step = 1

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def native_value(self) -> float:
        # Get internal index (0-12)
        idx = self._dataservice.get_flame_height()
        
        # If idx is 0 (Pilot), we return 0 (which is below min, showing "Off" effectively on some UIs, or just 0)
        # If idx is > 0, we map it directly. (Index 1 = Level 1)
        return float(idx)

    async def async_set_native_value(self, value: float) -> None:
        # User selects 1-12. This maps directly to Index 1-12.
        # They cannot select 0 (Pilot) here anymore.
        index = int(value)
        await self._dataservice.async_set_flame_height(index)

    @property
    def icon(self) -> str:
        return "mdi:fire"
