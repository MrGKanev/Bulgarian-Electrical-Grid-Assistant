
"""Constants for the ERP Power Interruption Monitor integration."""

DOMAIN = "erp_power_monitor"
CONF_ADDRESSES = "addresses"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 86400  # 24 hours in seconds

# URL to scrape
URL = "https://www.erpsever.bg/bg/prekysvanija"

# Attributes
ATTR_MATCHED_ADDRESS = "matched_address"
ATTR_INTERRUPTION_DATE = "interruption_date"
ATTR_INTERRUPTION_TIME = "interruption_time"
ATTR_AFFECTED_ADDRESSES = "affected_addresses"

# Sensor names
BINARY_SENSOR_NAME = "Power Interruption Alert"
SENSOR_NAME = "Power Interruption Details"