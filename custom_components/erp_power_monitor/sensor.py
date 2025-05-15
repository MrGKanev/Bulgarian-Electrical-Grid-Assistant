"""Sensor platform for ERP Power Interruption Monitor."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_NAME,
    ATTR_INTERRUPTION_DATE,
    ATTR_INTERRUPTION_TIME,
    ATTR_AFFECTED_ADDRESSES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([ERPPowerInterruptionSensor(coordinator)])


class ERPPowerInterruptionSensor(CoordinatorEntity, SensorEntity):
    """Sensor for power interruption details."""

    _attr_has_entity_name = True

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_power_interruption_details"
        self._attr_name = SENSOR_NAME

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.coordinator.data or not self.coordinator.data["matched"]:
            return "No interruptions"
        
        match = self.coordinator.matched_addresses[0]  # Get first match
        return f"Interruption on {match['date']} at {match['time']}"

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attrs = {}
        
        if self.coordinator.data and self.coordinator.matched_addresses:
            match = self.coordinator.matched_addresses[0]  # Get first match
            attrs[ATTR_INTERRUPTION_DATE] = match["date"]
            attrs[ATTR_INTERRUPTION_TIME] = match["time"]
            attrs[ATTR_AFFECTED_ADDRESSES] = match["addresses"]
        
        return attrs