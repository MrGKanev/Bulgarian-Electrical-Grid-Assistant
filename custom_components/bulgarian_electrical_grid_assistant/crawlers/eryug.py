"""ERYUG power interruption crawler."""
import logging
from bs4 import BeautifulSoup

from .base import BaseCrawler
from ..const import URL_ERYUG_PLANNED, URL_ERYUG_UNPLANNED

_LOGGER = logging.getLogger(__name__)

class ERYUGCrawler(BaseCrawler):
    """Crawler for ERYUG power interruption data."""

    def __init__(self, hass):
        """Initialize the crawler."""
        super().__init__(hass)
        self._provider_name = "ERYUG"
    
    async def async_get_interruptions(self):
        """Fetch and parse interruption data from ERYUG website."""
        # Get both planned and unplanned interruptions
        interruptions = []
        
        # Fetch planned interruptions
        planned_html = await self.async_fetch_url(URL_ERYUG_PLANNED)
        if planned_html:
            planned = await self.hass.async_add_executor_job(
                self.parse_interruptions, planned_html, "planned"
            )
            interruptions.extend(planned)
        
        # Fetch unplanned interruptions
        unplanned_html = await self.async_fetch_url(URL_ERYUG_UNPLANNED)
        if unplanned_html:
            unplanned = await self.hass.async_add_executor_job(
                self.parse_interruptions, unplanned_html, "unplanned"
            )
            interruptions.extend(unplanned)
        
        return interruptions
    
    def parse_interruptions(self, html, interruption_type):
        """Parse the HTML content to extract interruption data."""
        interruptions = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find the region tabs
        region_tabs = soup.find_all("div", class_="tab-pane")
        
        if not region_tabs:
            _LOGGER.warning(f"Could not find region tabs on the ERYUG {interruption_type} page")
            return []
        
        # Process each region tab
        for tab in region_tabs:
            region_id = tab.get("id")
            if not region_id:
                continue
            
            region_name = region_id  # Default to ID if name not found
            
            # Look for a heading with the region name
            heading = soup.find("a", attrs={"href": f"#{region_id}"})
            if heading:
                region_name = heading.text.strip()
            
            # Find all tables in this region tab
            tables = tab.find_all("table", class_="table")
            
            for table in tables:
                # Process table rows
                rows = table.find_all("tr")
                if len(rows) <= 1:  # Skip if only header row or empty
                    continue
                
                # Extract data from each row
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all("td")
                    if len(cells) < 5:  # Ensure we have all needed cells
                        continue
                    
                    # Extract data from cells
                    # Expected format: Oblast, KEC, Address(es), Timeframe (from/to), Date(s)
                    oblast = cells[0].text.strip() if len(cells) > 0 else ""
                    kec = cells[1].text.strip() if len(cells) > 1 else ""
                    addresses_text = cells[2].text.strip() if len(cells) > 2 else ""
                    time_range = cells[3].text.strip() if len(cells) > 3 else ""
                    dates = cells[4].text.strip() if len(cells) > 4 else ""
                    
                    # Split addresses by new lines or commas if multiple
                    addresses = [addr.strip() for addr in addresses_text.replace("\n", ",").split(",") if addr.strip()]
                    
                    if addresses:
                        interruptions.append({
                            "date": dates,
                            "time": time_range,
                            "region": region_name,
                            "oblast": oblast,
                            "kec": kec,
                            "addresses": addresses,
                            "provider": self.provider_name,
                            "type": interruption_type
                        })
        
        return interruptions