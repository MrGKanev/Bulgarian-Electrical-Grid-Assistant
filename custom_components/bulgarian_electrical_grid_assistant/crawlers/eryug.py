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
        interruptions = []
        
        try:
            # Fetch planned interruptions
            planned_html = await self.async_fetch_url(URL_ERYUG_PLANNED)
            if planned_html:
                planned = await self.hass.async_add_executor_job(
                    self.parse_interruptions, planned_html, "planned"
                )
                interruptions.extend(planned)
            else:
                _LOGGER.warning("Failed to fetch planned interruptions from ERYUG")
            
            # Fetch unplanned interruptions
            unplanned_html = await self.async_fetch_url(URL_ERYUG_UNPLANNED)
            if unplanned_html:
                unplanned = await self.hass.async_add_executor_job(
                    self.parse_interruptions, unplanned_html, "unplanned"
                )
                interruptions.extend(unplanned)
            else:
                _LOGGER.warning("Failed to fetch unplanned interruptions from ERYUG")
            
            # Validate and filter interruptions
            valid_interruptions = []
            for interruption in interruptions:
                if self._validate_interruption_data(interruption):
                    valid_interruptions.append(interruption)
                else:
                    _LOGGER.warning(f"Skipping invalid interruption data from ERYUG: {interruption}")
            
            _LOGGER.info(f"ERYUG crawler found {len(valid_interruptions)} valid interruptions out of {len(interruptions)} total")
            return valid_interruptions
            
        except Exception as error:
            _LOGGER.error(f"Error in ERYUG crawler: {error}", exc_info=True)
            return []
    
    def parse_interruptions(self, html, interruption_type):
        """Parse the HTML content to extract interruption data."""
        interruptions = []
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Find the region tabs
            region_tabs = soup.find_all("div", class_="tab-pane")
            
            if not region_tabs:
                _LOGGER.warning(f"Could not find region tabs on the ERYUG {interruption_type} page")
                return []
            
            # Process each region tab
            for tab in region_tabs:
                region_interruptions = self._process_region_tab(tab, soup, interruption_type)
                interruptions.extend(region_interruptions)
                
        except Exception as error:
            _LOGGER.error(f"Error parsing ERYUG {interruption_type} HTML: {error}", exc_info=True)
        
        return interruptions
    
    def _process_region_tab(self, tab, soup, interruption_type):
        """Process a single region tab to extract interruptions."""
        interruptions = []
        
        try:
            region_id = tab.get("id")
            if not region_id:
                return []
            
            region_name = self._get_region_name(soup, region_id)
            
            # Find all tables in this region tab
            tables = tab.find_all("table", class_="table")
            
            for table in tables:
                table_interruptions = self._process_table(table, region_name, interruption_type)
                interruptions.extend(table_interruptions)
                
        except Exception as error:
            _LOGGER.error(f"Error processing region tab: {error}")
        
        return interruptions
    
    def _get_region_name(self, soup, region_id):
        """Get the region name from the tab heading."""
        try:
            heading = soup.find("a", attrs={"href": f"#{region_id}"})
            if heading:
                return heading.get_text(strip=True)
        except Exception as error:
            _LOGGER.debug(f"Could not find region name for {region_id}: {error}")
        
        return region_id  # Default to ID if name not found
    
    def _process_table(self, table, region_name, interruption_type):
        """Process a table to extract interruption data."""
        interruptions = []
        
        try:
            rows = table.find_all("tr")
            if len(rows) <= 1:  # Skip if only header row or empty
                return []
            
            # Extract data from each row (skip header)
            for i, row in enumerate(rows[1:], 1):
                try:
                    interruption = self._process_table_row(row, region_name, interruption_type)
                    if interruption:
                        interruptions.append(interruption)
                except Exception as error:
                    _LOGGER.error(f"Error processing table row {i}: {error}")
                    continue
                    
        except Exception as error:
            _LOGGER.error(f"Error processing table: {error}")
        
        return interruptions
    
    def _process_table_row(self, row, region_name, interruption_type):
        """Process a single table row to extract interruption data."""
        try:
            cells = row.find_all("td")
            if len(cells) < 5:  # Ensure we have all needed cells
                return None
            
            # Extract data from cells
            # Expected format: Oblast, KEC, Address(es), Timeframe (from/to), Date(s)
            oblast = cells[0].get_text(strip=True) if len(cells) > 0 else ""
            kec = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            addresses_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            time_range = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            dates = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            
            # Validate that we have essential data
            if not addresses_text or not dates:
                _LOGGER.debug(f"Skipping row with missing essential data: addresses='{addresses_text}', dates='{dates}'")
                return None
            
            # Process addresses
            addresses = self._parse_addresses(addresses_text)
            if not addresses:
                _LOGGER.debug(f"No valid addresses found in: {addresses_text}")
                return None
            
            # Create interruption data
            interruption_data = {
                "date": dates,
                "time": time_range or "Unknown time",
                "region": region_name,
                "oblast": oblast,
                "kec": kec,
                "addresses": addresses,
                "provider": self.provider_name,
                "type": interruption_type
            }
            
            return interruption_data
            
        except Exception as error:
            _LOGGER.error(f"Error processing table row: {error}")
            return None
    
    def _parse_addresses(self, addresses_text):
        """Parse and clean address text into a list of addresses."""
        addresses = []
        
        try:
            # Split addresses by common separators
            raw_addresses = []
            
            # First try splitting by newlines
            if '\n' in addresses_text:
                raw_addresses = addresses_text.split('\n')
            # Then try splitting by semicolons
            elif ';' in addresses_text:
                raw_addresses = addresses_text.split(';')
            # Then try splitting by commas (but be careful as addresses might contain commas)
            elif ',' in addresses_text and addresses_text.count(',') > 1:
                raw_addresses = addresses_text.split(',')
            else:
                # Single address
                raw_addresses = [addresses_text]
            
            # Clean and validate each address
            for addr in raw_addresses:
                cleaned = addr.strip()
                if cleaned and len(cleaned) > 2:  # Minimum reasonable address length
                    # Normalize whitespace
                    normalized = ' '.join(cleaned.split())
                    addresses.append(normalized)
                    
        except Exception as error:
            _LOGGER.error(f"Error parsing addresses from '{addresses_text}': {error}")
        
        return addresses