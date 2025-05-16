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
        html = await self.async_fetch_url(URL_ERP)
        if not html:
            return []
        
        return await self.hass.async_add_executor_job(self.parse_interruptions, html)
    
    def parse_interruptions(self, html):
        """Parse the HTML content to extract interruption data."""
        interruptions = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find the map areas (the regions of Bulgaria)
        region_map = soup.find("ul", id="interruption_areas", class_="interruption-areas")
        
        if not region_map:
            _LOGGER.warning("Could not find the map regions on the ERP page")
            # Fallback to the old method
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
                    "region": region_id,
                    "addresses": addresses,
                    "provider": self.provider_name,
                    "type": "planned"  # ERP only has planned interruptions
                })
        
        # If we found no interruptions with the map method, try the fallback method
        if not interruptions:
            return self._parse_wrappers(soup)
            
        return interruptions
        
    def _parse_wrappers(self, soup):
        """Fallback method to parse wrappers directly if map regions aren't found."""
        interruptions = []
        
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
                    "provider": self.provider_name,
                    "type": "planned"  # ERP only has planned interruptions
                })
        
        return interruptions