"""Sensor platform for Bulgarian Electrical Grid Assistant."""
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
    ATTR_PROVIDER,
    ATTR_TYPE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities([PowerInterruptionSensor(coordinator)])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload sensor entities."""
    return True


class PowerInterruptionSensor(CoordinatorEntity, SensorEntity):
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
        if (not self.coordinator.data or 
            not self.coordinator.data.get("matched") or 
            not self.coordinator.matched_addresses):
            return "No interruptions"
        
        match = self.coordinator.matched_addresses[0]  # Get first match
        provider = match.get("provider", "")
        interruption_type = match.get("type", "planned")
        date = match.get("date", "Unknown date")
        time = match.get("time", "Unknown time")
        
        return f"{provider} {interruption_type} interruption on {date} at {time}"

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attrs = {}
        
        if (self.coordinator.data and 
            self.coordinator.data.get("matched") and 
            self.coordinator.matched_addresses):
            match = self.coordinator.matched_addresses[0]  # Get first match
            attrs[ATTR_INTERRUPTION_DATE] = match.get("date", "Unknown")
            attrs[ATTR_INTERRUPTION_TIME] = match.get("time", "Unknown")
            attrs[ATTR_AFFECTED_ADDRESSES] = match.get("addresses", [])
            attrs[ATTR_PROVIDER] = match.get("provider", "")
            attrs[ATTR_TYPE] = match.get("type", "planned")
        
        return attrs