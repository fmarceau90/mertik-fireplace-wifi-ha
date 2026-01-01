import logging
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    device_name = entry.data["name"]
    async_add_entities([
        MertikBatterySensor(dataservice, entry.entry_id, device_name),
        MertikProblemSensor(dataservice, entry.entry_id, device_name),
    ])

class MertikBatterySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Receiver Battery"
        self._attr_unique_id = entry_id + "-battery"
        self._attr_device_class = BinarySensorDeviceClass.BATTERY

    @property
    def is_on(self):
        # For Binary Sensor BATTERY class:
        # ON means "Low Battery" (Problem)
        # OFF means "Normal"
        return self._dataservice.mertik._low_battery
        
    @property
    def device_info(self):
        return self._dataservice.device_info

class MertikProblemSensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Error Status"
        self._attr_unique_id = entry_id + "-problem"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        # If "Guard Flame" is active, it usually means safety shutoff triggered
        return self._dataservice.mertik._guard_flame_on

    @property
    def device_info(self):
        return self._dataservice.device_info
