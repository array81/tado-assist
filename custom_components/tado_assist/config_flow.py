import logging 
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Available options for the update interval
SCAN_INTERVAL_OPTIONS = {
    "15_seconds": 15,  # Option for 15 seconds
    "30_seconds": 30,  # Option for 30 seconds
    "1_minute": 60,  # Option for 1 minute
    "2_minutes": 120,  # Option for 2 minutes
    "5_minutes": 300,  # Option for 5 minutes
}

class TadoAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # Handle the configuration flow for Tado Assist

    VERSION = 1  # Set the version of the configuration flow

    async def async_step_user(self, user_input=None):
        # Handle the initial configuration step
        errors = {}  # Initialize an empty dictionary to store any errors

        if user_input is not None:  # If the user has provided input
            username = user_input[CONF_USERNAME]  # Extract the username from user input
            password = user_input[CONF_PASSWORD]  # Extract the password from user input
            scan_interval = SCAN_INTERVAL_OPTIONS[user_input["scan_interval"]]  # Convert the selected scan interval to its corresponding value

            try:
                # Simulate logging into Tado to validate the credentials
                from .tado_api import TadoAPI
                tado = TadoAPI(self.hass, username, password)
                await tado.async_login()

                # Use the username to generate a unique device ID
                await self.async_set_unique_id(f"tado_assist_{username}")
                self._abort_if_unique_id_configured()

                # Create and return the configuration entry with the user input data
                return self.async_create_entry(
                    title="Tado Assist",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        "scan_interval": scan_interval,
                    },
                )
            except Exception as err:
                _LOGGER.error("Error during Tado login test: %s", err)
                errors["base"] = "cannot_connect"

        # Define the schema for the configuration form, requiring username, password, and scan interval
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(
                "scan_interval",
                default="15_seconds"
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(SCAN_INTERVAL_OPTIONS.keys()),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="scan_interval"
                )
            )
        })

        # Show the configuration form to the user, passing the schema and any errors
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return TadoAssistOptionsFlowHandler(config_entry)  # Return the options flow handler for the configuration entry

class TadoAssistOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the options flow for Tado Assist."""

    def __init__(self, config_entry):
        """Initialize the options flow handler."""
        self.entry_id = config_entry.entry_id  # Store the entry ID for this configuration

    async def async_step_init(self, user_input=None):
        """Handle the options for the integration."""
        if user_input is not None:  # If the user has provided input
            return self.async_create_entry(title="", data=user_input)  # Create an entry with the user-provided data

        # Define the schema for the options form, requiring username, password, and scan interval
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(
                "scan_interval",
                default="15_seconds"
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(SCAN_INTERVAL_OPTIONS.keys()),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="scan_interval"
                )
            )
        })

        # Show the options form to the user, passing the schema
        return self.async_show_form(step_id="init", data_schema=data_schema)
