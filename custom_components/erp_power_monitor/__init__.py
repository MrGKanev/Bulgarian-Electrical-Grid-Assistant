"""ERP Power Interruption Monitor integration."""
import logging
from datetime import timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import (
    DOMAIN,
    URL,
    DEFAULT_SCAN_INTERVAL,
    CONF_ADDRESSES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ERP Power Interruption Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Get configuration
    addresses = entry.options.get(CONF_ADDRESSES, entry.data.get(CONF_ADDRESSES, []))
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    
    # Create update coordinator
    coordinator = ERPDataUpdateCoordinator(
        hass,
        _LOGGER,
        addresses=addresses,
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


class ERPDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching ERP Power Interruption data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        addresses: list,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.addresses = addresses
        self.matched_addresses = []
        self.all_interruptions = []
        
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
        )
    
    async def _async_update_data(self):
        """Fetch data from ERP website."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error fetching data: {response.status}")
                    
                    html = await response.text()
                    
                    # Parse the HTML content
                    interruptions = await self.hass.async_add_executor_job(
                        self.parse_interruptions, html
                    )
                    
                    # Check for matches
                    matched = []
                    for interruption in interruptions:
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
                                })
                    
                    self.matched_addresses = matched
                    self.all_interruptions = interruptions
                    
                    return {
                        "matched": matched,
                        "all_interruptions": interruptions,
                    }
                    
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            raise UpdateFailed(f"Error communicating with server: {error}")
    
    def parse_interruptions(self, html):
        """Parse the HTML content to extract interruption data."""
        interruptions = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all wrapper divs
        wrappers = soup.find_all("div", class_="wrapper")
        
        for wrapper in wrappers:
            # Extract the date and time if available
            date_elem = wrapper.find_previous(lambda tag: tag.name == "h3" and "date-title" in tag.get("class", []))
            date = date_elem.text.strip() if date_elem else "Unknown date"
            
            time_elem = wrapper.find_previous(lambda tag: tag.name == "div" and "hour-holder" in tag.get("class", []))
            time = time_elem.text.strip() if time_elem else "Unknown time"
            
            # Extract addresses
            addresses = []
            for address_elem in wrapper.find_all(["p", "div"], class_=lambda c: c and "address" in c):
                address_text = address_elem.text.strip()
                if address_text:
                    addresses.append(address_text)
            
            if addresses:
                interruptions.append({
                    "date": date,
                    "time": time,
                    "addresses": addresses,
                })
        
        return interruptions