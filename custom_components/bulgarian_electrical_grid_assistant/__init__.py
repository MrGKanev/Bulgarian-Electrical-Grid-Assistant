"""Bulgarian Electrical Grid Assistant integration."""
import logging
from datetime import timedelta
import asyncio
import re
from typing import List, Dict, Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_SCAN_INTERVAL, Platform

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_ADDRESSES,
    CONF_PROVIDERS,
    DEFAULT_PROVIDERS,
)
from .crawlers import ERPCrawler, ERYUGCrawler

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

class PowerInterruptionDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching power interruption data from multiple providers."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        addresses: List[str],
        providers: List[str],
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.addresses = addresses
        self.providers = providers
        self.matched_addresses = []
        self.all_interruptions = []
        
        # Rate limiting - track last request time per provider
        self._last_request_times = {}
        self._min_request_interval = 60  # Minimum 1 minute between requests per provider
        
        # Initialize crawlers with error handling
        self.crawlers = {}
        try:
            if "ERP" in providers:
                self.crawlers["ERP"] = ERPCrawler(hass)
            if "ERYUG" in providers:
                self.crawlers["ERYUG"] = ERYUGCrawler(hass)
        except Exception as err:
            logger.error("Error initializing crawlers: %s", err)
        
        # Precompile address patterns for better performance
        self._address_patterns = self._prepare_address_patterns(addresses)
        
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
        )
    
    def _prepare_address_patterns(self, addresses: List[str]) -> List[Dict[str, Any]]:
        """Prepare address patterns for efficient matching."""
        patterns = []
        
        # Bulgarian address keywords with their variations
        bulgarian_address_words = {
            'улица': ['ул', 'улица'],
            'булевард': ['бул', 'булевард'],
            'площад': ['пл', 'площад'],
            'квартал': ['кв', 'квартал'],
            'жилищен комплекс': ['жк'],
            'блок': ['бл', 'блок'],
        }
        
        for addr in addresses:
            # Normalize the address
            normalized = self._normalize_address(addr)
            
            # Extract significant words (skip common words)
            words = self._extract_significant_words(normalized)
            
            # Create pattern dictionary
            pattern = {
                'original': addr,
                'normalized': normalized,
                'words': words,
                'length': len(normalized)
            }
            patterns.append(pattern)
            
        return patterns
    
    def _normalize_address(self, address: str) -> str:
        """Normalize address for consistent matching."""
        if not address:
            return ""
        
        # Convert to lowercase and normalize whitespace
        normalized = re.sub(r'\s+', ' ', address.lower().strip())
        
        # Normalize common Bulgarian abbreviations
        replacements = {
            r'\bул\b': 'улица',
            r'\bбул\b': 'булевард',
            r'\bпл\b': 'площад',
            r'\bкв\b': 'квартал',
            r'\bжк\b': 'жилищен комплекс',
            r'\bбл\b': 'блок',
        }
        
        for pattern, replacement in replacements.items():
            normalized = re.sub(pattern, replacement, normalized)
        
        return normalized
    
    def _extract_significant_words(self, address: str) -> set:
        """Extract significant words from an address."""
        if not address:
            return set()
        
        # Split into words and filter
        words = address.split()
        
        # Remove common non-distinctive words
        stop_words = {
            'улица', 'булевард', 'площад', 'квартал', 'жилищен', 'комплекс',
            'блок', 'вход', 'апартамент', 'етаж', 'и', 'в', 'на', 'до', 'от'
        }
        
        # Keep only significant words (length > 2, not stop words, not numbers)
        significant = set()
        for word in words:
            if (len(word) > 2 and 
                word not in stop_words and 
                not word.isdigit() and
                not (len(word) == 3 and word.isdigit())):  # Skip 3-digit numbers
                significant.add(word)
        
        return significant
    
    def _is_address_match(self, user_pattern: Dict[str, Any], affected_address: str) -> bool:
        """Check if user address matches affected address using improved logic."""
        if not affected_address:
            return False
        
        affected_normalized = self._normalize_address(affected_address)
        affected_words = self._extract_significant_words(affected_normalized)
        
        # Strategy 1: Exact normalized match
        if user_pattern['normalized'] == affected_normalized:
            return True
        
        # Strategy 2: One address is contained in the other (with length check)
        if (user_pattern['normalized'] in affected_normalized or 
            affected_normalized in user_pattern['normalized']):
            # Only match if the shorter address is at least 50% of the longer
            min_len = min(len(user_pattern['normalized']), len(affected_normalized))
            max_len = max(len(user_pattern['normalized']), len(affected_normalized))
            if min_len / max_len >= 0.5:
                return True
        
        # Strategy 3: Significant word overlap
        if user_pattern['words'] and affected_words:
            overlap = user_pattern['words'].intersection(affected_words)
            user_word_count = len(user_pattern['words'])
            affected_word_count = len(affected_words)
            
            # Require at least 2 word matches, or 1 if both addresses have only 1 significant word
            if user_word_count == 1 and affected_word_count == 1:
                return len(overlap) >= 1
            else:
                return len(overlap) >= 2
        
        return False
    
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from all enabled provider websites."""
        try:
            if not self.crawlers:
                self.logger.warning("No providers enabled or no crawlers available")
                return {"matched": [], "all_interruptions": []}
            
            # Enforce rate limiting
            current_time = self.hass.loop.time()
            for provider in self.crawlers:
                last_time = self._last_request_times.get(provider, 0)
                if current_time - last_time < self._min_request_interval:
                    self.logger.debug(f"Rate limiting {provider}, skipping this update")
                    # Return cached data if available
                    return {
                        "matched": self.matched_addresses,
                        "all_interruptions": self.all_interruptions,
                    }
            
            # Update request times
            for provider in self.crawlers:
                self._last_request_times[provider] = current_time
            
            # Run all crawler requests concurrently with timeout
            tasks = []
            crawler_names = []
            for name, crawler in self.crawlers.items():
                task = asyncio.wait_for(
                    crawler.async_get_interruptions(), 
                    timeout=30.0  # 30 second timeout per crawler
                )
                tasks.append(task)
                crawler_names.append(name)
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            all_interruptions = []
            successful_providers = []
            failed_providers = []
            
            for i, result in enumerate(results):
                provider_name = crawler_names[i]
                
                if isinstance(result, asyncio.TimeoutError):
                    self.logger.error(f"Timeout fetching data from {provider_name}")
                    failed_providers.append(provider_name)
                elif isinstance(result, Exception):
                    self.logger.error(f"Error fetching data from {provider_name}: {result}")
                    failed_providers.append(provider_name)
                elif isinstance(result, list):
                    # Validate each interruption
                    valid_interruptions = []
                    for interruption in result:
                        if self._validate_interruption_data(interruption):
                            valid_interruptions.append(interruption)
                        else:
                            self.logger.warning(f"Invalid interruption data from {provider_name}")
                    
                    all_interruptions.extend(valid_interruptions)
                    successful_providers.append(provider_name)
                    self.logger.debug(f"Successfully fetched {len(valid_interruptions)} interruptions from {provider_name}")
                else:
                    self.logger.warning(f"Unexpected result type from {provider_name}: {type(result)}")
                    failed_providers.append(provider_name)
            
            # Log results
            if successful_providers:
                self.logger.info(f"Successfully updated from providers: {', '.join(successful_providers)}")
            if failed_providers:
                self.logger.warning(f"Failed to update from providers: {', '.join(failed_providers)}")
            
            # Find matches using improved algorithm
            matched = self._find_matches(all_interruptions)
            
            # Update instance variables (limit size to prevent memory issues)
            self.matched_addresses = matched[:50]  # Limit to 50 matches
            self.all_interruptions = all_interruptions[:200]  # Limit to 200 total interruptions
            
            return {
                "matched": matched,
                "all_interruptions": all_interruptions,
            }
                
        except Exception as error:
            self.logger.error(f"Unexpected error in coordinator update: {error}", exc_info=True)
            raise UpdateFailed(f"Error updating data: {error}")
    
    def _find_matches(self, all_interruptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find matches between user addresses and interruption addresses."""
        matched = []
        
        for interruption in all_interruptions:
            if not isinstance(interruption.get("addresses"), list):
                self.logger.warning(f"Invalid addresses format in interruption: {interruption}")
                continue
            
            # Check each user address pattern against interruption addresses
            for user_pattern in self._address_patterns:
                match_found = False
                
                for affected_address in interruption["addresses"]:
                    if self._is_address_match(user_pattern, affected_address):
                        matched.append({
                            "matched_address": user_pattern['original'],
                            "affected_address": affected_address,
                            "date": interruption.get("date", "Unknown"),
                            "time": interruption.get("time", "Unknown"),
                            "addresses": interruption["addresses"],
                            "provider": interruption.get("provider", ""),
                            "type": interruption.get("type", "planned")
                        })
                        match_found = True
                        break  # Avoid multiple matches for same user address in same interruption
                
                if match_found:
                    break  # Move to next interruption after finding a match
        
        return matched
    
    def _validate_interruption_data(self, interruption: Dict[str, Any]) -> bool:
        """Validate interruption data structure."""
        if not isinstance(interruption, dict):
            return False
        
        required_fields = ['date', 'time', 'addresses', 'provider', 'type']
        
        for field in required_fields:
            if field not in interruption or not interruption[field]:
                return False
        
        # Validate addresses
        addresses = interruption.get('addresses')
        if not isinstance(addresses, list) or len(addresses) == 0:
            return False
        
        # Validate each address
        for addr in addresses:
            if not isinstance(addr, str) or len(addr.strip()) < 3:
                return False
        
        # Validate type
        if interruption.get('type') not in ['planned', 'unplanned']:
            return False

        return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bulgarian Electrical Grid Assistant from a config entry."""

    # Get configuration from entry data and options (options override data)
    scan_interval = timedelta(
        seconds=entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
    )
    addresses = entry.options.get(
        CONF_ADDRESSES,
        entry.data.get(CONF_ADDRESSES, [])
    )
    providers = entry.options.get(
        CONF_PROVIDERS,
        entry.data.get(CONF_PROVIDERS, DEFAULT_PROVIDERS)
    )

    # Create the coordinator
    coordinator = PowerInterruptionDataCoordinator(
        hass=hass,
        logger=_LOGGER,
        addresses=addresses,
        providers=providers,
        update_interval=scan_interval,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in runtime_data (modern HA pattern)
    entry.runtime_data = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup listener for config updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)