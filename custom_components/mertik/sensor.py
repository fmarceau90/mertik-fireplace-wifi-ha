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
        MertikStatusSensor(dataservice, entry.entry_id, device_name), # <--- NEW
    ])

# 1. AMBIENT TEMP
class MertikTemperatureSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Ambient Temperature"
        self._attr_unique_id = entry_id + "-ambient-temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self):
        return self._dataservice.ambient_temperature

    @property
    def device_info(self):
        return self._dataservice.device_info

# 2. OPERATING MODE (0, 1, 2)
class MertikModeSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Operating Mode"
        self._attr_unique_id = entry_id + "-mode"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self):
        return self._dataservice.operating_mode

    @property
    def device_info(self):
        return self._dataservice.device_info

# 3. DETAILED STATUS (The Diagnostic Array)
class MertikStatusSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, dataservice, entry_id, name):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._attr_name = name + " Diagnostics"
        self._attr_unique_id = entry_id + "-diagnostics"
        self._attr_icon = "mdi:message-alert-outline"

    @property
    def native_value(self):
        """Return a human-readable summary of the highest priority state."""
        m = self._dataservice.mertik
        
        # Priority 1: Safety Lockouts
        if m._guard_flame_on:
            if m._low_battery:
                return "Error: Low Battery Lockout"
            return "Error: Safety Lockout (Guard)"
        
        # Priority 2: Transitions
        if m.is_igniting:
            return "Igniting..."
        if m.is_shutting_down:
            return "Shutting Down..."
            
        # Priority 3: Warnings
        if m._low_battery:
            return "Warning: Low Battery"
            
        # Priority 4: Normal Operation
        if m.flameHeight == 0:
            if m.is_on: # Should not happen often (On but 0 height usually means Pilot)
                 return "Pilot / Standby"
            return "Standby (Off)"
        
        return f"Heating (Level {m.flameHeight})"

    @property
    def extra_state_attributes(self):
        """Expose the raw flags for debugging."""
        m = self._dataservice.mertik
        return {
            "is_igniting": m.is_igniting,
            "is_shutting_down": m.is_shutting_down,
            "guard_flame_active": m._guard_flame_on,
            "low_battery": m._low_battery,
            "fan_active": m._fan_on,
            "rf_signal_level": m._rf_signal_level,
            "raw_mode_id": m.mode,
            "thermostat_active": self._dataservice.is_thermostat_active
        }

    @property
    def device_info(self):
        return self._dataservice.device_info
