"""Base crawler for power interruption providers."""
from abc import ABC, abstractmethod
import logging
import asyncio
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
    
    async def async_fetch_url(self, url, timeout=30):
        """Fetch HTML content from a URL with proper error handling."""
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            connector = aiohttp.TCPConnector(ssl=True, limit=10, limit_per_host=5)
            
            async with aiohttp.ClientSession(
                timeout=timeout_config,
                connector=connector
            ) as session:
                headers = {
                    'User-Agent': 'Home Assistant Bulgarian Grid Assistant/1.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'bg,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Check for reasonable content size (10MB limit)
                        if len(content) > 10 * 1024 * 1024:
                            _LOGGER.warning(f"Response from {url} is very large ({len(content)} bytes)")
                            return None
                        
                        # Basic validation that we got HTML content
                        if not content.strip():
                            _LOGGER.warning(f"Empty response from {url}")
                            return None
                            
                        _LOGGER.debug(f"Successfully fetched {len(content)} bytes from {url}")
                        return content
                        
                    elif response.status == 404:
                        _LOGGER.error(f"Page not found (404) at {url}")
                        return None
                    elif response.status == 403:
                        _LOGGER.error(f"Access forbidden (403) to {url}")
                        return None
                    elif response.status == 500:
                        _LOGGER.error(f"Server error (500) at {url}")
                        return None
                    else:
                        _LOGGER.error(f"HTTP {response.status} error fetching data from {url}")
                        return None
                        
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout ({timeout}s) fetching data from {url}")
            return None
        except aiohttp.ClientConnectorError as error:
            _LOGGER.error(f"Connection error to {url}: {error}")
            return None
        except aiohttp.ClientResponseError as error:
            _LOGGER.error(f"Response error from {url}: {error}")
            return None
        except aiohttp.ClientError as error:
            _LOGGER.error(f"Client error communicating with {url}: {error}")
            return None
        except UnicodeDecodeError as error:
            _LOGGER.error(f"Unicode decode error from {url}: {error}")
            return None
        except Exception as error:
            _LOGGER.error(f"Unexpected error fetching {url}: {error}")
            return None
    
    def _validate_interruption_data(self, interruption):
        """Validate interruption data before returning."""
        if not isinstance(interruption, dict):
            _LOGGER.warning("Interruption data must be a dictionary")
            return False
            
        required_fields = ['date', 'time', 'addresses', 'provider', 'type']
        
        for field in required_fields:
            if field not in interruption:
                _LOGGER.warning(f"Missing required field '{field}' in interruption data")
                return False
            
            if not interruption[field]:
                _LOGGER.warning(f"Empty value for required field '{field}' in interruption data")
                return False
        
        # Validate addresses is a list and not empty
        if not isinstance(interruption['addresses'], list):
            _LOGGER.warning("Addresses field must be a list")
            return False
            
        if len(interruption['addresses']) == 0:
            _LOGGER.warning("Addresses field cannot be empty")
            return False
        
        # Validate each address is a non-empty string
        for addr in interruption['addresses']:
            if not isinstance(addr, str) or not addr.strip():
                _LOGGER.warning(f"Invalid address format: {addr}")
                return False
        
        # Validate type is one of expected values
        if interruption['type'] not in ['planned', 'unplanned']:
            _LOGGER.warning(f"Invalid interruption type: {interruption['type']}")
            return False
        
        # Validate provider is a string
        if not isinstance(interruption['provider'], str):
            _LOGGER.warning(f"Provider must be a string: {interruption['provider']}")
            return False
        
        return True