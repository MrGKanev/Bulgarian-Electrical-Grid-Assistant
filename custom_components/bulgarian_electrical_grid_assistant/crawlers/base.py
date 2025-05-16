"""Base crawler for power interruption providers."""
from abc import ABC, abstractmethod
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

class BaseCrawler(ABC):
    """Base class for power interruption data crawlers."""

    def __init__(self, hass):
        """Initialize the crawler."""
        self.hass = hass
        self._provider_name = None
    
    @property
    def provider_name(self):
        """Return the name of the provider."""
        return self._provider_name
    
    @abstractmethod
    async def async_get_interruptions(self):
        """Fetch and parse interruption data from the provider website.
        
        Returns:
            list: A list of interruption dictionaries with the following keys:
                - date: Date of the interruption
                - time: Time range of the interruption
                - addresses: List of affected addresses
                - provider: Name of the provider
                - type: Type of interruption (planned/unplanned)
        """
        pass
    
    async def async_fetch_url(self, url):
        """Fetch HTML content from a URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Error fetching data from {url}: {response.status}")
                        return None
                    
                    return await response.text()
        except (aiohttp.ClientError, Exception) as error:
            _LOGGER.error(f"Error communicating with {url}: {error}")
            return None