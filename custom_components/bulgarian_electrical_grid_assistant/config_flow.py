"""Config flow for Bulgarian Electrical Grid Assistant integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_ADDRESSES,
    CONF_PROVIDERS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_PROVIDERS,
)


class PowerInterruptionFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bulgarian Electrical Grid Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate input
            if not user_input.get(CONF_ADDRESSES):
                errors[CONF_ADDRESSES] = "no_addresses"
            
            if not errors:
                # Process addresses string to list
                if CONF_ADDRESSES in user_input and isinstance(user_input[CONF_ADDRESSES], str):
                    addresses = [addr.strip() for addr in user_input[CONF_ADDRESSES].split(",")]
                    user_input[CONF_ADDRESSES] = addresses
                
                # Create entry
                return self.async_create_entry(
                    title="Bulgarian Electrical Grid Assistant",
                    data=user_input,
                )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESSES): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=3600)),  # Minimum 1 hour
                vol.Optional(
                    CONF_PROVIDERS, default=DEFAULT_PROVIDERS
                ): vol.All(cv.multi_select({"ERP": "ERP", "ERYUG": "ERYUG"})),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            # Process addresses string to list
            if CONF_ADDRESSES in user_input and isinstance(user_input[CONF_ADDRESSES], str):
                addresses = [addr.strip() for addr in user_input[CONF_ADDRESSES].split(",")]
                user_input[CONF_ADDRESSES] = addresses
            
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        addresses = self.config_entry.options.get(
            CONF_ADDRESSES, self.config_entry.data.get(CONF_ADDRESSES, [])
        )
        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        providers = self.config_entry.options.get(
            CONF_PROVIDERS, self.config_entry.data.get(CONF_PROVIDERS, DEFAULT_PROVIDERS)
        )
        
        # Convert list to comma-separated string for display
        if isinstance(addresses, list):
            addresses = ", ".join(addresses)

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESSES, default=addresses): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=scan_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=3600)),  # Minimum 1 hour
                vol.Optional(
                    CONF_PROVIDERS, default=providers
                ): vol.All(cv.multi_select({"ERP": "ERP", "ERYUG": "ERYUG"})),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )