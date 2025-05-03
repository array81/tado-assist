"""Tado Assist Integration."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.issue_registry import async_create_issue, async_delete_issue, IssueSeverity

from .switch import TadoGeoreferencingSwitch, TadoWindowControlSwitch
from .const import DOMAIN
from .tado_api import TadoAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tado Assist from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("tado_assist_status", True)
    hass.data[DOMAIN].setdefault("tado_georeferencing_status", False)
    hass.data[DOMAIN].setdefault("tado_window_control_status", False)

    scan_interval = timedelta(seconds=entry.data.get("scan_interval", 15))
    refresh_token = entry.data.get("refresh_token")

    _LOGGER.info("Caricamento Tado Assist con refresh_token: %s", refresh_token)

    tado = TadoAPI(hass, entry, refresh_token=refresh_token)

    try:
        status_result = await tado.async_initialize()
    except ConfigEntryAuthFailed as err:
        _LOGGER.warning("TadoAPI: authentication failed, triggering reauth.")
        raise ConfigEntryAuthFailed("Autenticazione non riuscita, reauth necessaria.") from err

    status = status_result.get("status")
    if not status:
        _LOGGER.error("Tado authentication status is missing.")
        return False

    new_token = tado.get_refresh_token()
    if new_token and new_token != refresh_token:
        _LOGGER.info("New refresh_token obtained, updating config_entry.")
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "refresh_token": new_token},
        )

    if status == "NOT_STARTED":
        _LOGGER.error(
            "Tado authentication flow has not started. Please reconfigure the integration from the Home Assistant UI."
        )
        raise ConfigEntryAuthFailed("Authentication not started.")

    elif status == "PENDING":
        _LOGGER.warning(
            "Tado authentication is still pending. Complete the authentication via the provided URL and device code."
        )
        raise ConfigEntryAuthFailed("Authentication pending.")

    elif status != "COMPLETED":
        _LOGGER.error(f"Tado returned unexpected authentication status: {status}")
        return False

    hass.data[DOMAIN]["tado"] = tado

    async def async_update_data():
        """Fetch the latest data from Tado servers."""

        if not hass.data[DOMAIN]["tado_assist_status"]:
            _LOGGER.info("Tado Assist is disabled, skipping data update.")
            return hass.data[DOMAIN].get("last_data", {})

        _LOGGER.debug("Fetching data from Tado...")

        try:
            home_state = await tado.get_home_state() or {}
            mobile_devices = await tado.get_mobile_devices() or 0
            open_window_zones = await tado.get_open_window_detected() or []

            open_window_zone_ids = [zone["id"] for zone in open_window_zones]
            open_window_zone_names = [zone["name"] for zone in open_window_zones]
        except Exception as e:
            _LOGGER.error("Failed to fetch data from Tado: %s", e)
            return hass.data[DOMAIN].get("last_data", {})

        tado_georeferencing_status = any(
            isinstance(entity, TadoGeoreferencingSwitch) and entity.is_on
            for entity in hass.data[DOMAIN].get("switch_entities", [])
        )

        tado_window_control_status = any(
            isinstance(entity, TadoWindowControlSwitch) and entity.is_on
            for entity in hass.data[DOMAIN].get("switch_entities", [])
        )

        new_data = {
            "home_state": home_state,
            "mobile_devices": mobile_devices,
            "open_window_zone_ids": open_window_zone_ids,
            "open_window_zone_names": open_window_zone_names,
            "tado_georeferencing_status": tado_georeferencing_status,
            "tado_window_control_status": tado_window_control_status,
        }

        hass.data[DOMAIN]["last_data"] = new_data

        if new_data["tado_georeferencing_status"]:
            for entity in hass.data[DOMAIN].get("switch_entities", []):
                if isinstance(entity, TadoGeoreferencingSwitch):
                    await entity.async_check_and_set_home_or_away()

        if new_data["tado_window_control_status"]:
            for entity in hass.data[DOMAIN].get("switch_entities", []):
                if isinstance(entity, TadoWindowControlSwitch):
                    await entity.async_check_and_pause_thermostat()

        # 🔁 Salva refresh_token aggiornato
        try:
            status = await hass.async_add_executor_job(tado._tado.device_activation_status)
            if status == "COMPLETED":
                new_token = tado.get_refresh_token()
                if new_token and new_token != entry.data.get("refresh_token"):
                    _LOGGER.info("New refresh token detected during update, saving.")
                    hass.config_entries.async_update_entry(
                        entry, data={**entry.data, "refresh_token": new_token}
                    )
        except Exception as e:
            _LOGGER.error("Error saving updated refresh token: %s", e)

        return new_data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Tado Assist",
        update_method=async_update_data,
        update_interval=scan_interval,
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, ["binary_sensor", "switch"])

    async_delete_issue(hass, DOMAIN, issue_id="auth_not_started")
    async_delete_issue(hass, DOMAIN, issue_id="auth_pending")

    _LOGGER.info("Tado Assist integration set up successfully.")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Tado Assist config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["binary_sensor", "switch"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
