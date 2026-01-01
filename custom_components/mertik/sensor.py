from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    entities = []

    # Temp Sensor
    entities.append(
        MertikAmbientTemperatureSensorEntity(
            hass, dataservice, entry.entry_id, entry.data["name"]
        )
    )
    
    # Mode Sensor (New!)
    entities.append(
        MertikModeSensorEntity(
            hass, dataservice, entry.entry_id, entry.data["name"]
        )
    )

    async_add_entities(entities)


class MertikAmbientTemperatureSensorEntity(CoordinatorEntity, SensorEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Ambient Temperature"
        self._device_class = "temperature"
        self._attr_unique_id = entry_id + "-AmbientTemperature"

    @property
    def device_info(self):
        return self._dataservice.device_info

    @property
    def native_value(self):
        return self._dataservice.ambient_temperature

    @property
    def native_unit_of_measurement(self) -> str:
        return UnitOfTemperature.CELSIUS

class MertikModeSensorEntity(CoordinatorEntity, SensorEntity):
    def __init__(self, hass, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Operating Mode"
        self._attr_unique_id = entry_id + "-OperatingMode"
        self._attr_icon = "mdi:information-outline"

    @property
    def device_info(self):
        return self._dataservice.device_info
        
    @property
    def native_value(self):
        return self._dataservice.operating_mode
