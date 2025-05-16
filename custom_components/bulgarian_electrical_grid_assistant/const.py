"""Constants for the Bulgarian Electrical Grid Assistant integration."""

DOMAIN = "bulgarian_electrical_grid_assistant"
CONF_ADDRESSES = "addresses"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PROVIDERS = "providers"
DEFAULT_SCAN_INTERVAL = 86400  # 24 hours in seconds
DEFAULT_PROVIDERS = ["ERP", "ERYUG"]

# URLs to scrape
URL_ERP = "https://www.erpsever.bg/bg/prekysvanija"
URL_ERYUG_PLANNED = "https://www.elyug.bg/Customers/Planned_shutdowns.aspx"
URL_ERYUG_UNPLANNED = "https://www.elyug.bg/Customers/Unscheduled-power-cuts.aspx"

# Attributes
ATTR_MATCHED_ADDRESS = "matched_address"
ATTR_INTERRUPTION_DATE = "interruption_date"
ATTR_INTERRUPTION_TIME = "interruption_time"
ATTR_AFFECTED_ADDRESSES = "affected_addresses"
ATTR_PROVIDER = "provider"
ATTR_TYPE = "type"

# Sensor names
BINARY_SENSOR_NAME = "Power Interruption Alert"
SENSOR_NAME = "Power Interruption Details"