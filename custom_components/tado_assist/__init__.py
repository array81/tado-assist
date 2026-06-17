"""Tado Assist Integration."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.issue_registry import async_delete_issue

from .switch import TadoGeoreferencingSwitch, TadoWindowControlSwitch, TadoAwaySwitch
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .tado_api import TadoAPI, TadoAuthError, TadoApiError

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tado Assist from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("tado_assist_status", True)
    hass.data[DOMAIN].setdefault("tado_georeferencing_status", False)
    hass.data[DOMAIN].setdefault("tado_window_control_status", False)

    scan_interval = timedelta(seconds=entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL))
    refresh_token = entry.data.get("refresh_token")

    _LOGGER.info("Caricamento Tado Assist con refresh_token: %s", refresh_token)

    tado = TadoAPI(hass, entry, refresh_token=refresh_token)

    try:
        status_result = await tado.async_initialize()
    except (TadoAuthError, ConfigEntryAuthFailed) as err:
        _LOGGER.warning("TadoAPI: authentication failed, triggering reauth.")
        raise ConfigEntryAuthFailed("Autenticazione non riuscita, reauth necessaria.") from err
    except TadoApiError as err:
        # QUESTO È IL FIX: Se all'avvio Tado ci blocca per il Rate Limit o non c'è internet,
        # diciamo ad HA di riprovare più tardi in background.
        _LOGGER.warning("Server Tado non pronto o Rate Limit raggiunto all'avvio. Riprovo più tardi...")
        raise ConfigEntryNotReady(f"Impossibile comunicare con Tado all'avvio: {err}") from err
    except Exception as err:
        # Cattura qualsiasi altro errore imprevisto
        _LOGGER.error("Errore generico durante l'inizializzazione: %s", err)
        raise ConfigEntryNotReady(f"Errore generico: {err}") from err

    status = status_result.get("status")
    
    if status in ["NOT_STARTED", "PENDING"]:
        _LOGGER.error("Il flusso Tado non è completato. Riconfigurare l'integrazione.")
        raise ConfigEntryAuthFailed("Authentication non completata.")

    elif status != "COMPLETED":
        _LOGGER.error(f"Tado ha restituito uno stato inatteso: {status}")
        return False

    hass.data[DOMAIN]["tado"] = tado

    async def async_update_data():
        """Fetch the latest data from Tado servers."""

        if not hass.data[DOMAIN]["tado_assist_status"]:
            return hass.data[DOMAIN].get("last_data", {})

        try:
            home_state = await tado.get_home_state() or {}
            mobile_devices = await tado.get_mobile_devices() or 0
            open_window_zones = await tado.get_open_window_detected() or []

            open_window_zone_ids = [zone["id"] for zone in open_window_zones]
            open_window_zone_names = [zone["name"] for zone in open_window_zones]
            
        except (TadoAuthError, ConfigEntryAuthFailed) as e:
            # QUESTO SALVA DAL CRASH: se il token muore definitivamente (revocato/scaduto per sempre)
            _LOGGER.warning("Token scaduto in modo permanente, avvio Repair flow.")
            raise ConfigEntryAuthFailed("Token non più valido, richiesta riconfigurazione.") from e
            
        except Exception as e:
            # Se siamo in Rate Limit (429) o manca internet, diciamo ad HA che l'aggiornamento è fallito!
            # HA metterà le entità in "Non disponibile" e rallenterà automaticamente le chiamate per non farsi bannare.
            _LOGGER.error("Errore di comunicazione con Tado: %s", e)
            raise UpdateFailed(f"Errore di comunicazione: {e}") from e

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

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Tado Assist config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["binary_sensor", "switch"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok