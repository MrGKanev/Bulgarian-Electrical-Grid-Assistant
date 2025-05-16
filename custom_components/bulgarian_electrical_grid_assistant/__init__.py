"""Bulgarian Electrical Grid Assistant integration."""
import logging
from datetime import timedelta
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_ADDRESSES,
    CONF_PROVIDERS,
    DEFAULT_PROVIDERS,
)
from .crawlers import ERPCrawler, ERYUGCrawler

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bulgarian Electrical Grid Assistant from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Get configuration
    addresses = entry.options.get(CONF_ADDRESSES, entry.data.get(CONF_ADDRESSES, []))
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    providers = entry.options.get(
        CONF_PROVIDERS, entry.data.get(CONF_PROVIDERS, DEFAULT_PROVIDERS)
    )
    
    # Create update coordinator
    coordinator = PowerInterruptionDataCoordinator(
        hass,
        _LOGGER,
        addresses=addresses,
        providers=providers,
        update_interval=timedelta(seconds=scan_interval),
    )
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Add update listener for options
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class PowerInterruptionDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching power interruption data from multiple providers."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        addresses: list,
        providers: list,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.addresses = addresses
        self.providers = providers
        self.matched_addresses = []
        self.all_interruptions = []
        
        # Initialize crawlers
        self.crawlers = {}
        if "ERP" in providers:
            self.crawlers["ERP"] = ERPCrawler(hass)
        if "ERYUG" in providers:
            self.crawlers["ERYUG"] = ERYUGCrawler(hass)
        
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
        )
    
    async def _async_update_data(self):
        """Fetch data from all enabled provider websites."""
        try:
            # Get interruptions from all providers
            all_interruptions = []
            
            # Run all crawler requests concurrently
            tasks = []
            for crawler in self.crawlers.values():
                tasks.append(crawler.async_get_interruptions())
            
            if not tasks:
                self.logger.warning("No providers enabled or no crawlers available")
                return {"matched": [], "all_interruptions": []}
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error fetching data: {result}")
                    continue
                
                all_interruptions.extend(result)
            
            # Check for matches
            matched = []
            for interruption in all_interruptions:
                for address in self.addresses:
                    # Check if any configured address is found in the interruption addresses
                    if any(
                        address.lower() in affected_address.lower()
                        for affected_address in interruption["addresses"]
                    ):
                        matched.append({
                            "matched_address": address,
                            "date": interruption["date"],
                            "time": interruption["time"],
                            "addresses": interruption["addresses"],
                            "provider": interruption["provider"],
                            "type": interruption.get("type", "planned")
                        })
            
            self.matched_addresses = matched
            self.all_interruptions = all_interruptions
            
            return {
                "matched": matched,
                "all_interruptions": all_interruptions,
            }
                
        except Exception as error:
            raise UpdateFailed(f"Error updating data: {error}")