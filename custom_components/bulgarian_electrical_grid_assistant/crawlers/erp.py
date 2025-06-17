"""ERP power interruption crawler."""
import logging
from bs4 import BeautifulSoup

from .base import BaseCrawler
from ..const import URL_ERP

_LOGGER = logging.getLogger(__name__)

class ERPCrawler(BaseCrawler):
    """Crawler for ERP power interruption data."""

    def __init__(self, hass):
        """Initialize the crawler."""
        super().__init__(hass)
        self._provider_name = "ERP"
    
    async def async_get_interruptions(self):
        """Fetch and parse interruption data from ERP website."""
        try:
            html = await self.async_fetch_url(URL_ERP)
            if not html:
                _LOGGER.warning("Failed to fetch data from ERP website")
                return []
            
            interruptions = await self.hass.async_add_executor_job(self.parse_interruptions, html)
            
            # Validate and filter interruptions
            valid_interruptions = []
            for interruption in interruptions:
                if self._validate_interruption_data(interruption):
                    valid_interruptions.append(interruption)
                else:
                    _LOGGER.warning(f"Skipping invalid interruption data from ERP: {interruption}")
            
            _LOGGER.info(f"ERP crawler found {len(valid_interruptions)} valid interruptions out of {len(interruptions)} total")
            return valid_interruptions
            
        except Exception as error:
            _LOGGER.error(f"Error in ERP crawler: {error}", exc_info=True)
            return []
    
    def parse_interruptions(self, html):
        """Parse the HTML content to extract interruption data."""
        interruptions = []
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Find the map areas (the regions of Bulgaria)
            region_map = soup.find("ul", id="interruption_areas", class_="interruption-areas")
            
            if not region_map:
                _LOGGER.warning("Could not find the map regions on the ERP page, trying fallback method")
                return self._parse_wrappers(soup)
            
            # Process each region
            for region in region_map.find_all("li"):
                region_id = region.get("id")
                if not region_id:
                    continue
                    
                # Find the associated wrapper for this region
                wrapper = soup.find("div", id=f"wrapper_{region_id}")
                if not wrapper:
                    continue
                
                # Extract interruption data for this region
                region_interruptions = self._extract_region_data(soup, wrapper, region_id)
                interruptions.extend(region_interruptions)
            
            # If we found no interruptions with the map method, try the fallback method
            if not interruptions:
                _LOGGER.info("No interruptions found with map method, trying fallback")
                return self._parse_wrappers(soup)
                
            return interruptions
            
        except Exception as error:
            _LOGGER.error(f"Error parsing ERP HTML: {error}", exc_info=True)
            return []
        
    def _extract_region_data(self, soup, wrapper, region_id):
        """Extract interruption data for a specific region."""
        interruptions = []
        
        try:
            # Extract the date and time if available
            date_elem = wrapper.find_previous(lambda tag: tag.name == "h3" and "date-title" in tag.get("class", []))
            date = date_elem.text.strip() if date_elem else "Unknown date"
            
            time_elem = wrapper.find_previous(lambda tag: tag.name == "div" and "hour-holder" in tag.get("class", []))
            time = time_elem.text.strip() if time_elem else "Unknown time"
            
            # Extract addresses
            addresses = self._extract_addresses(wrapper)
            
            if addresses:
                interruption_data = {
                    "date": date,
                    "time": time,
                    "region": region_id,
                    "addresses": addresses,
                    "provider": self.provider_name,
                    "type": "planned"  # ERP only has planned interruptions
                }
                interruptions.append(interruption_data)
                
        except Exception as error:
            _LOGGER.error(f"Error extracting data for region {region_id}: {error}")
        
        return interruptions
        
    def _parse_wrappers(self, soup):
        """Fallback method to parse wrappers directly if map regions aren't found."""
        interruptions = []
        
        try:
            # Find all wrapper divs
            wrappers = soup.find_all("div", class_="wrapper")
            
            for i, wrapper in enumerate(wrappers):
                try:
                    # Extract the date and time if available
                    date_elem = wrapper.find_previous(lambda tag: tag.name == "h3" and "date-title" in tag.get("class", []))
                    date = date_elem.text.strip() if date_elem else "Unknown date"
                    
                    time_elem = wrapper.find_previous(lambda tag: tag.name == "div" and "hour-holder" in tag.get("class", []))
                    time = time_elem.text.strip() if time_elem else "Unknown time"
                    
                    # Extract addresses
                    addresses = self._extract_addresses(wrapper)
                    
                    if addresses:
                        interruption_data = {
                            "date": date,
                            "time": time,
                            "addresses": addresses,
                            "provider": self.provider_name,
                            "type": "planned"  # ERP only has planned interruptions
                        }
                        interruptions.append(interruption_data)
                        
                except Exception as error:
                    _LOGGER.error(f"Error processing wrapper {i}: {error}")
                    continue
        
        except Exception as error:
            _LOGGER.error(f"Error in fallback wrapper parsing: {error}")
        
        return interruptions
    
    def _extract_addresses(self, wrapper):
        """Extract addresses from a wrapper element."""
        addresses = []
        
        try:
            # Look for address elements with various class patterns
            address_selectors = [
                ["p", "div"],  # tag types
                lambda c: c and "address" in c.lower()  # class filter
            ]
            
            for address_elem in wrapper.find_all(address_selectors[0], class_=address_selectors[1]):
                address_text = address_elem.get_text(strip=True)
                if address_text and len(address_text) > 2:  # Minimum reasonable address length
                    # Clean up the address text
                    cleaned_address = ' '.join(address_text.split())  # Normalize whitespace
                    addresses.append(cleaned_address)
            
            # If no addresses found with class filter, try broader search
            if not addresses:
                for elem in wrapper.find_all(["p", "div", "span"]):
                    text = elem.get_text(strip=True)
                    # Basic heuristic to identify address-like text
                    if (text and 
                        len(text) > 5 and 
                        len(text) < 200 and 
                        any(keyword in text.lower() for keyword in ['ул', 'бул', 'кв', 'улица', 'булевард'])):
                        cleaned_text = ' '.join(text.split())
                        addresses.append(cleaned_text)
            
        except Exception as error:
            _LOGGER.error(f"Error extracting addresses: {error}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_addresses = []
        for addr in addresses:
            if addr not in seen:
                seen.add(addr)
                unique_addresses.append(addr)
        
        return unique_addresses