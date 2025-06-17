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
    
    def _is_address_match(self, user_address: str, affected_address: str) -> bool:
        """Check if user address matches affected address."""
        if not user_address or not affected_address:
            return False
            
        user_addr_clean = user_address.lower().strip()
        affected_addr_clean = affected_address.lower().strip()
        
        # Direct match
        if user_addr_clean == affected_addr_clean:
            return True
        
        # Check if user address is contained in affected address (original logic)
        if user_addr_clean in affected_addr_clean:
            return True
        
        # Split addresses into words and check for significant word matches
        user_words = set(word for word in user_addr_clean.split() if len(word) > 2)
        affected_words = set(word for word in affected_addr_clean.split() if len(word) > 2)
        
        # Remove common Bulgarian address words that shouldn't be used for matching
        common_words = {
            'ул', 'улица', 'бул', 'булевард', 'пл', 'площад', 'кв', 'квартал',
            'жк', 'блок', 'бл', 'вх', 'вход', 'ап', 'апартамент', 'етаж', 'ет'
        }
        user_words -= common_words
        affected_words -= common_words
        
        # If we have significant words, require at least 2 to match
        if len(user_words) >= 2 and len(affected_words) >= 2:
            matches = user_words.intersection(affected_words)
            return len(matches) >= 2
        elif len(user_words) == 1 and len(affected_words) >= 1:
            # If user has only one significant word, check if it matches
            return bool(user_words.intersection(affected_words))
        
        return False
    
    async def _async_update_data(self):
        """Fetch data from all enabled provider websites."""
        try:
            # Get interruptions from all providers
            all_interruptions = []
            
            if not self.crawlers:
                self.logger.warning("No providers enabled or no crawlers available")
                return {"matched": [], "all_interruptions": []}
            
            # Run all crawler requests concurrently
            tasks = []
            crawler_names = []
            for name, crawler in self.crawlers.items():
                tasks.append(crawler.async_get_interruptions())
                crawler_names.append(name)
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results with better error handling
            successful_providers = []
            failed_providers = []
            
            for i, result in enumerate(results):
                provider_name = crawler_names[i]
                if isinstance(result, Exception):
                    self.logger.error(f"Error fetching data from {provider_name}: {result}")
                    failed_providers.append(provider_name)
                    continue
                
                if isinstance(result, list):
                    all_interruptions.extend(result)
                    successful_providers.append(provider_name)
                    self.logger.debug(f"Successfully fetched {len(result)} interruptions from {provider_name}")
                else:
                    self.logger.warning(f"Unexpected result type from {provider_name}: {type(result)}")
                    failed_providers.append(provider_name)
            
            if successful_providers:
                self.logger.info(f"Successfully updated from providers: {', '.join(successful_providers)}")
            if failed_providers:
                self.logger.warning(f"Failed to update from providers: {', '.join(failed_providers)}")
            
            # Check for matches
            matched = []
            for interruption in all_interruptions:
                if not isinstance(interruption.get("addresses"), list):
                    self.logger.warning(f"Invalid addresses format in interruption: {interruption}")
                    continue
                    
                for user_address in self.addresses:
                    # Check if any configured address matches the interruption addresses
                    for affected_address in interruption["addresses"]:
                        if self._is_address_match(user_address, affected_address):
                            matched.append({
                                "matched_address": user_address,
                                "date": interruption.get("date", "Unknown"),
                                "time": interruption.get("time", "Unknown"),
                                "addresses": interruption["addresses"],
                                "provider": interruption.get("provider", ""),
                                "type": interruption.get("type", "planned")
                            })
                            # Break to avoid multiple matches for the same user address
                            break
                    # Break outer loop if we found a match for this user address
                    else:
                        continue
                    break
            
            self.matched_addresses = matched
            self.all_interruptions = all_interruptions
            
            return {
                "matched": matched,
                "all_interruptions": all_interruptions,
            }
                
        except Exception as error:
            self.logger.error(f"Unexpected error in coordinator update: {error}", exc_info=True)
            raise UpdateFailed(f"Error updating data: {error}")