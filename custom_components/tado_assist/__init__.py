"""""Tado Assist Integration."""

import asyncio
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .switch import TadoGeoreferencingSwitch, TadoWindowControlSwitch
from .const import DOMAIN
from .tado_api import TadoAPI

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tado Assist from a config entry."""
    
    # Ensure the integration has a storage dictionary in hass.data
    hass.data.setdefault(DOMAIN, {})

    # ✅ Set default values to prevent key errors
    hass.data[DOMAIN].setdefault("tado_assist_status", True)
    hass.data[DOMAIN].setdefault("tado_georeferencing_status", False)
    hass.data[DOMAIN].setdefault("tado_window_control_status", False)

    # Retrieve credentials and scan interval from the config entry
    username = entry.data["username"]
    password = entry.data["password"]
    scan_interval = timedelta(seconds=entry.data.get("scan_interval", 15))  # Default: 15 seconds

    # Initialize Tado API client
    tado = TadoAPI(hass, username, password)
    await tado.async_login()  # Perform asynchronous login

    # Store the Tado API instance for global access
    hass.data[DOMAIN]["tado"] = tado

    async def async_update_data():
        """Update Tado data (home status, mobile devices, open windows)."""
        
        # Skip update if Tado Assist is disabled
        if not hass.data[DOMAIN]["tado_assist_status"]:
            _LOGGER.info("Tado Assist is deactivated, no update performed.")
            return hass.data[DOMAIN].get("last_data", {})

        _LOGGER.info("Updating data from Tado servers...")

        try:
            # Fetch data from Tado API using synchronous calls wrapped in async
            home_state = await hass.async_add_executor_job(tado.get_home_state) or {}
            mobile_devices = await hass.async_add_executor_job(tado.get_mobile_devices) or 0
            open_window_zones = await hass.async_add_executor_job(tado.get_open_window_detected) or []

            # Extract open window zone IDs and names
            open_window_zone_ids = [zone["id"] for zone in open_window_zones]
            open_window_zone_names = [zone["name"] for zone in open_window_zones]
        except Exception as e:
            _LOGGER.error("Error updating Tado data: %s", e)
            return hass.data[DOMAIN].get("last_data", {})

        _LOGGER.debug(open_window_zone_ids)
        _LOGGER.debug(open_window_zone_names)

        # Determine the status of Tado switches
        tado_georeferencing_status = False
        for entity in hass.data[DOMAIN].get("switch_entities", []):
            if isinstance(entity, TadoGeoreferencingSwitch) and entity.is_on:
                tado_georeferencing_status = True
                
        window_control_switch = False
        for entity in hass.data[DOMAIN].get("switch_entities", []):
            if isinstance(entity, TadoWindowControlSwitch) and entity.is_on:
                window_control_switch = True
                
        # Save the new data state
        new_data = {
            "home_state": home_state,
            "mobile_devices": mobile_devices,
            "open_window_zone_ids": open_window_zone_ids,
            "open_window_zone_names": open_window_zone_names,
            "tado_georeferencing_status": tado_georeferencing_status,
            "tado_window_control_status": window_control_switch
        }
        hass.data[DOMAIN]["last_data"] = new_data

        # If the geofencing switch is enabled, check and update home/away status
        if new_data["tado_georeferencing_status"]:
            for entity in hass.data[DOMAIN].get("switch_entities", []):
                if isinstance(entity, TadoGeoreferencingSwitch):
                    await entity.async_check_and_set_home_or_away()

        # If window control is enabled, check and pause thermostat if needed
        if new_data["tado_window_control_status"]:
            switch_entities = hass.data[DOMAIN].get("switch_entities", [])
            for entity in switch_entities:
                if isinstance(entity, TadoWindowControlSwitch):
                    await entity.async_check_and_pause_thermostat()

        return new_data

    # Create a DataUpdateCoordinator for scheduled updates
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Tado Assist",
        update_method=async_update_data,
        update_interval=scan_interval,
    )

    # Store the coordinator for this entry
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Perform the first update immediately
    await coordinator.async_config_entry_first_refresh()

    # Load necessary platforms (binary_sensor and switch)
    await hass.config_entries.async_forward_entry_setups(entry, ["binary_sensor", "switch"])

    _LOGGER.info("Tado Assist successfully configured!")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of a config entry."""
    
    # Unload associated platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["binary_sensor", "switch"])
    
    # If unloading was successful, remove entry from hass.data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    
    return unload_ok