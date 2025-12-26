"""Binary sensor platform for Bulgarian Electrical Grid Assistant."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    BINARY_SENSOR_NAME,
    ATTR_MATCHED_ADDRESS,
    ATTR_INTERRUPTION_DATE,
    ATTR_INTERRUPTION_TIME,
    ATTR_PROVIDER,
    ATTR_TYPE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities([PowerInterruptionBinarySensor(coordinator)])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload binary sensor entities."""
    return True


class PowerInterruptionBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for power interruption detection."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_power_interruption"
        self._attr_name = BINARY_SENSOR_NAME

    @property
    def is_on(self):
        """Return True if there's a power interruption scheduled for the configured address."""
        if not self.coordinator.data or not self.coordinator.data.get("matched"):
            return False
        return len(self.coordinator.data["matched"]) > 0

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attrs = {}
        
        if (self.is_on and 
            self.coordinator.matched_addresses and 
            len(self.coordinator.matched_addresses) > 0):
            match = self.coordinator.matched_addresses[0]  # Get first match
            attrs[ATTR_MATCHED_ADDRESS] = match.get("matched_address", "")
            attrs[ATTR_INTERRUPTION_DATE] = match.get("date", "Unknown")
            attrs[ATTR_INTERRUPTION_TIME] = match.get("time", "Unknown")
            attrs[ATTR_PROVIDER] = match.get("provider", "")  
            attrs[ATTR_TYPE] = match.get("type", "planned")
        
        return attrs