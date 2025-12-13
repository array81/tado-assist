import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_SCAN_INTERVAL, UnitOfTime
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL
from .tado_api import TadoAPI

_LOGGER = logging.getLogger(__name__)

# --- 1. OPTIONS FLOW HANDLER ---
class TadoAssistOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Gestisce le opzioni.
    """

    async def async_step_init(self, user_input=None):
        """Gestisce il modulo delle opzioni."""
        
        # FIX: Usiamo la nostra variabile 'saved_config_entry' invece di 'config_entry'
        # per evitare conflitti con le proprietà di sola lettura di Home Assistant.
        entry = getattr(self, "saved_config_entry", None)
        
        # Recupero sicuro del valore attuale
        current_interval = DEFAULT_SCAN_INTERVAL
        if entry and hasattr(entry, "data"):
            current_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        
        # Se l'utente ha inviato il modulo con nuovi dati
        if user_input is not None:
            if entry:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_SCAN_INTERVAL: user_input["scan_interval"]}
                )
            return self.async_create_entry(title="", data=user_input)

        # Mostra il modulo
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("scan_interval", default=int(current_interval)): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=3600,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=UnitOfTime.SECONDS
                    )
                )
            })
        )


# --- 2. CONFIG FLOW PRINCIPALE ---
class TadoAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """
        Crea il flusso opzioni.
        """
        # Creiamo l'istanza
        flow = TadoAssistOptionsFlowHandler()
        
        # FIX CRUCIALE: Salviamo l'entry in una variabile con nome DIVERSO
        # Non usare 'flow.config_entry' perché è protetta (read-only).
        flow.saved_config_entry = config_entry
        
        return flow

    def __init__(self):
        self.tado = None
        self._auth_url = None
        self._reauth_entry = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if not self.tado:
            self.tado = TadoAPI(self.hass, config_entries)

        try:
            status_result = await self.tado.async_initialize(force_new=False)
            status = status_result.get("status")
            self._auth_url = status_result.get("auth_url")

            if status in ["NOT_STARTED", "PENDING"]:
                return await self.async_step_activation()
            elif status == "COMPLETED":
                return await self.async_step_config()
        except Exception:
            errors["base"] = "unknown"

        return self.async_show_form(step_id="user", errors=errors)

    async def async_step_activation(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                success = await self.tado.async_activate_device()
                if success:
                    return await self._handle_post_auth()
                errors["base"] = "activation_failed"
            except Exception:
                errors["base"] = "unknown"

        if not self._auth_url:
             res = await self.tado.async_initialize(force_new=False)
             self._auth_url = res.get("auth_url")

        return self.async_show_form(
            step_id="activation",
            description_placeholders={"auth_url": self._auth_url},
            errors=errors
        )

    async def _handle_post_auth(self):
        if self._reauth_entry:
            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={**self._reauth_entry.data, "refresh_token": self.tado.get_refresh_token()}
            )
            self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        return await self.async_step_config()

    async def async_step_config(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Tado Assist",
                data={
                    CONF_SCAN_INTERVAL: user_input["scan_interval"],
                    "refresh_token": self.tado.get_refresh_token(),
                }
            )

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema({
                vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL): NumberSelector(
                    NumberSelectorConfig(min=MIN_SCAN_INTERVAL, max=3600, mode=NumberSelectorMode.BOX)
                )
            })
        )

    async def async_step_reauth(self, entry_data):
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self.tado = TadoAPI(self.hass, config_entries, refresh_token=entry_data.get("refresh_token"))
        await self.tado.async_initialize(force_new=False)
        return await self.async_step_reauth_activation()

    async def async_step_reauth_activation(self, user_input=None):
        errors = {}
        if user_input is not None:
            if await self.tado.async_activate_device():
                return await self._handle_post_auth()
            errors["base"] = "activation_failed"

        if not self._auth_url:
            res = await self.tado.async_initialize(force_new=True)
            self._auth_url = res.get("auth_url")

        return self.async_show_form(
            step_id="reauth_activation",
            description_placeholders={"auth_url": self._auth_url},
            errors=errors
        )