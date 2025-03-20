import voluptuous as vol  # Import the Voluptuous library for schema validation
from homeassistant import config_entries  # Import Home Assistant's config_entries module for handling configuration flows
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL  # Import constants, such as the domain and default scan interval

class TadoOptionsFlowHandler(config_entries.OptionsFlow):
    # Handle Tado options

    def __init__(self, config_entry):
        # Initialize options flow
        self.config_entry = config_entry  # Store the config entry object for reference

    async def async_step_init(self, user_input=None):
        # Manage the options
        errors = {}  # Initialize an empty dictionary to store any validation errors

        if user_input is not None:  # If the user has provided input
            return self.async_create_entry(title="", data=user_input)  # Create an entry with the user's input

        # Define a dictionary of scan interval options with corresponding human-readable labels
        OPTIONS = {
            15: "15 seconds",
            30: "30 seconds",
            60: "1 minute",
            120: "2 minutes",
            300: "5 minutes"
        }

        # Define the schema for the configuration form, requiring a valid scan interval from the options
        data_schema = vol.Schema({
            vol.Required("scan_interval", default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)): vol.In(OPTIONS)  # Validate scan_interval input
        })

        # Show the configuration form to the user, passing in the schema and any errors (if any)
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)  # Display the form for the user to configure options
