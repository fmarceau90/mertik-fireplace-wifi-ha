import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    device_name = entry.data["name"]
    async_add_entities([
        MertikTemperatureSensor(dataservice, entry.entry_id, device_name),
        MertikModeSensor(dataservice, entry.entry_id, device_name),
    ])

class MertikTemperatureSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Ambient Temperature"
        self._attr_unique_id = entry_id + "-ambient-temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        # suggested_display_precision=1 looks nicer in UI
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self):
        return self._dataservice.ambient_temperature

    @property
    def device_info(self):
        return self._dataservice.device_info

class MertikModeSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Operating Mode"
        self._attr_unique_id = entry_id + "-mode"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self):
        # Raw mode from device (usually "0", "1", "2")
        return self._dataservice.operating_mode

    @property
    def device_info(self):
        return self._dataservice.device_info
