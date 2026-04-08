"""Sensor platform for BlueBolt UPS."""

import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define sensor types with names and units
SENSOR_TYPES = {
    "watts": ("UPS Watts", "W", None),
    "volts_in": ("UPS Input Voltage", "V", SensorDeviceClass.VOLTAGE),
    "volts_out": ("UPS Output Voltage", "V", SensorDeviceClass.VOLTAGE),
    "current": ("UPS Current", "A", SensorDeviceClass.CURRENT),
    "battery": ("UPS Battery Level", "%", SensorDeviceClass.BATTERY),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up UPS sensors."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api = entry_data["api"]
    coordinator = entry_data["coordinator"]

    sensors = [
        UPSPowerSensor(coordinator, api, metric, name, unit, device_class)
        for metric, (name, unit, device_class) in SENSOR_TYPES.items()
    ]

    async_add_entities(sensors, False)


class UPSPowerSensor(CoordinatorEntity, SensorEntity):
    """UPS Power Sensors."""

    _attr_should_poll = False

    def __init__(self, coordinator, api, metric, name, unit, device_class):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._metric = metric
        self._attr_name = name
        self._attr_unique_id = f"ups_{metric}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "power_data" in self.coordinator.data:
            power_data = self.coordinator.data["power_data"]
            if self._metric in power_data:
                return power_data[self._metric]
        return None
