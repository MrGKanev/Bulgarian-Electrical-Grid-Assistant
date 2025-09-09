"""Base crawler for power interruption providers."""
from abc import ABC, abstractmethod
import logging
import asyncio
import aiohttp
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

_LOGGER = logging.getLogger(__name__)

class BaseCrawler(ABC):
    """Base class for power interruption data crawlers with improved resilience."""

    def __init__(self, hass):
        """Initialize the crawler."""
        self.hass = hass
        self._provider_name = None
        
        # Caching to reduce load on external websites
        self._cache = {}
        self._cache_duration = timedelta(minutes=30)  # Cache for 30 minutes
        
        # Circuit breaker pattern
        self._failure_count = 0
        self._max_failures = 3
        self._circuit_breaker_reset_time = None
        self._circuit_breaker_timeout = timedelta(minutes=15)  # 15 minute timeout
        
        # Request retry configuration
        self._max_retries = 2
        self._retry_delay = 5  # seconds
    
    @property
    def provider_name(self):
        """Return the name of the provider."""
        return self._provider_name
    
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        if not cache_entry:
            return False
        
        cache_time = cache_entry.get('timestamp')
        if not cache_time:
            return False
        
        return datetime.now() - cache_time < self._cache_duration
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open (preventing requests)."""
        if self._failure_count < self._max_failures:
            return False
        
        if (self._circuit_breaker_reset_time and 
            datetime.now() > self._circuit_breaker_reset_time):
            # Reset circuit breaker
            self._failure_count = 0
            self._circuit_breaker_reset_time = None
            _LOGGER.info(f"Circuit breaker reset for {self.provider_name}")
            return False
        
        return True
    
    def _record_success(self):
        """Record successful request."""
        self._failure_count = 0
        self._circuit_breaker_reset_time = None
    
    def _record_failure(self):
        """Record failed request."""
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._circuit_breaker_reset_time = datetime.now() + self._circuit_breaker_timeout
            _LOGGER.warning(
                f"Circuit breaker opened for {self.provider_name} after {self._failure_count} failures. "
                f"Will retry after {self._circuit_breaker_reset_time}"
            )
    
    @abstractmethod
    async def async_get_interruptions(self) -> List[Dict[str, Any]]:
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
    
    async def async_fetch_url(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch HTML content from a URL with resilience features."""
        
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            _LOGGER.warning(f"Circuit breaker is open for {self.provider_name}, skipping request to {url}")
            return None
        
        # Check cache first
        cache_key = self._get_cache_key(url)
        cache_entry = self._cache.get(cache_key)
        
        if self._is_cache_valid(cache_entry):
            _LOGGER.debug(f"Returning cached content for {url}")
            return cache_entry['content']
        
        # Try to fetch with retries
        for attempt in range(self._max_retries + 1):
            try:
                content = await self._fetch_url_attempt(url, timeout)
                if content:
                    # Cache successful response
                    self._cache[cache_key] = {
                        'content': content,
                        'timestamp': datetime.now()
                    }
                    
                    # Clean old cache entries
                    self._cleanup_cache()
                    
                    self._record_success()
                    return content
                    
            except Exception as error:
                _LOGGER.error(f"Attempt {attempt + 1} failed for {url}: {error}")
                
                if attempt < self._max_retries:
                    wait_time = self._retry_delay * (2 ** attempt)  # Exponential backoff
                    _LOGGER.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    self._record_failure()
        
        return None
    
    async def _fetch_url_attempt(self, url: str, timeout: int) -> Optional[str]:
        """Single attempt to fetch URL content."""
        
        # Validate URL
        if not url or not url.startswith(('http://', 'https://')):
            _LOGGER.error(f"Invalid URL: {url}")
            return None
        
        timeout_config = aiohttp.ClientTimeout(total=timeout, connect=10)
        
        # Use more restrictive SSL and connection settings
        connector = aiohttp.TCPConnector(
            ssl=True,
            limit=5,  # Reduced connection pool size
            limit_per_host=2,  # Max 2 connections per host
            ttl_dns_cache=300,  # DNS cache for 5 minutes
            use_dns_cache=True,
        )
        
        try:
            async with aiohttp.ClientSession(
                timeout=timeout_config,
                connector=connector,
                headers={
                    'User-Agent': f'Home Assistant Bulgarian Grid Assistant/{self.provider_name}/1.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'bg,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'no-cache',  # Prevent stale content
                }
            ) as session:
                
                async with session.get(url) as response:
                    # Check response status
                    if response.status == 200:
                        content = await response.text()
                        
                        # Validate content
                        if not self._is_valid_content(content, url):
                            return None
                            
                        _LOGGER.debug(f"Successfully fetched {len(content)} bytes from {url}")
                        return content
                        
                    elif response.status == 429:  # Rate limited
                        _LOGGER.error(f"Rate limited by {url}")
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=429
                        )
                    elif response.status == 503:  # Service unavailable
                        _LOGGER.error(f"Service unavailable: {url}")
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=503
                        )
                    elif response.status in (404, 403):
                        _LOGGER.error(f"Access denied or not found (HTTP {response.status}): {url}")
                        return None
                    else:
                        _LOGGER.error(f"HTTP {response.status} error fetching data from {url}")
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
                        
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout ({timeout}s) fetching data from {url}")
            raise
        except aiohttp.ClientConnectorError as error:
            _LOGGER.error(f"Connection error to {url}: {error}")
            raise
        except aiohttp.ClientResponseError as error:
            if error.status == 429:  # Rate limited, should retry later
                raise
            _LOGGER.error(f"Response error from {url}: {error}")
            raise
        except Exception as error:
            _LOGGER.error(f"Unexpected error fetching {url}: {error}")
            raise
    
    def _is_valid_content(self, content: str, url: str) -> bool:
        """Validate that the content is reasonable."""
        if not content or not content.strip():
            _LOGGER.warning(f"Empty content from {url}")
            return False
        
        # Check for reasonable content size (between 100 bytes and 10MB)
        content_size = len(content)
        if content_size < 100:
            _LOGGER.warning(f"Content too small ({content_size} bytes) from {url}")
            return False
        
        if content_size > 10 * 1024 * 1024:  # 10MB limit
            _LOGGER.warning(f"Content too large ({content_size} bytes) from {url}")
            return False
        
        # Basic HTML validation
        if not any(tag in content.lower() for tag in ['<html', '<body', '<div', '<table']):
            _LOGGER.warning(f"Content doesn't appear to be HTML from {url}")
            return False
        
        # Check for error pages (common patterns)
        error_indicators = ['404 not found', '403 forbidden', '500 internal server', 'error occurred']
        if any(indicator in content.lower() for indicator in error_indicators):
            _LOGGER.warning(f"Content appears to be an error page from {url}")
            return False
        
        return True
    
    def _cleanup_cache(self):
        """Remove expired cache entries to prevent memory leaks."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if current_time - entry['timestamp'] > self._cache_duration:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            _LOGGER.debug(f"Cleaned up {len(expired_keys)} expired cache entries for {self.provider_name}")
    
    def _validate_interruption_data(self, interruption: Dict[str, Any]) -> bool:
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
        addresses = interruption.get('addresses')
        if not isinstance(addresses, list):
            _LOGGER.warning("Addresses field must be a list")
            return False
            
        if len(addresses) == 0:
            _LOGGER.warning("Addresses field cannot be empty")
            return False
        
        # Validate each address is a non-empty string with reasonable length
        for addr in addresses:
            if not isinstance(addr, str):
                _LOGGER.warning(f"Invalid address type: {type(addr)}")
                return False
            
            addr_clean = addr.strip()
            if len(addr_clean) < 3:
                _LOGGER.warning(f"Address too short: '{addr}'")
                return False
            
            if len(addr_clean) > 200:  # Reasonable max length
                _LOGGER.warning(f"Address too long: '{addr[:50]}...'")
                return False
        
        # Validate type is one of expected values
        if interruption['type'] not in ['planned', 'unplanned']:
            _LOGGER.warning(f"Invalid interruption type: {interruption['type']}")
            return False
        
        # Validate provider is a string
        provider = interruption.get('provider')
        if not isinstance(provider, str) or not provider.strip():
            _LOGGER.warning(f"Invalid provider: {provider}")
            return False
        
        # Validate date and time are strings (can be "Unknown" but not empty)
        for time_field in ['date', 'time']:
            value = interruption.get(time_field)
            if not isinstance(value, str) or not value.strip():
                _LOGGER.warning(f"Invalid {time_field}: {value}")
                return False
        
        return True