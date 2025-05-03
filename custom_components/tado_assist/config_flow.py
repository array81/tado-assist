import logging
import voluptuous as vol
import asyncio  # Assicurati che sia importato in alto

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN
from .tado_api import TadoAPI

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_OPTIONS = {
    "15_seconds": 15,
    "30_seconds": 30,
    "1_minute": 60,
    "2_minutes": 120,
    "5_minutes": 300,
}


class TadoAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.tado = None
        self._auth_url = None
        self._reauth_entry = None
        self.scan_interval = SCAN_INTERVAL_OPTIONS["15_seconds"]

    async def async_step_user(self, user_input=None):
        _LOGGER.info("async_step_user called. user_input: %s", user_input)
        errors = {}

        if not self.tado:
            self.tado = TadoAPI(self.hass, config_entries)

        try:
            status_result = await self.tado.async_initialize(force_new=False)
            status = status_result["status"]
            self._auth_url = status_result.get("auth_url")

            _LOGGER.info("Tado status: %s, auth_url: %s", status_result, self._auth_url)

            if status in ["NOT_STARTED", "PENDING"]:
                return await self.async_step_activation()
            elif status == "COMPLETED":
                return await self.async_step_config()

        except Exception as e:
            _LOGGER.exception("Errore durante lo step user: %s", e)
            errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}), errors=errors)

    async def async_step_activation(self, user_input=None):
        _LOGGER.info("Entrato in async_step_activation con user_input=%s", user_input)

        try:
            if user_input is not None:
                _LOGGER.info("Tentativo di attivazione in corso...")
                success = await self.tado.async_activate_device()

                if success:
                    _LOGGER.info("Attivazione completata con successo.")
                    return await self._handle_post_authentication()

            # Controllo stato attuale
            status_result = await self.tado.async_initialize(force_new=False)
            status = status_result["status"]

            if status == "COMPLETED":
                _LOGGER.info("Token attivo trovato, si passa alla configurazione.")
                return await self._handle_post_authentication()

            # Mostra il link per completare l'autenticazione
            self._auth_url = status_result.get("auth_url")
            _LOGGER.info("Mostro il form con auth_url: %s", self._auth_url)

            return self.async_show_form(
                step_id="activation",
                data_schema=vol.Schema({}),
                description_placeholders={"auth_url": self._auth_url},
            )

        except Exception as e:
            _LOGGER.exception("Errore durante lo step activation: %s", e)
            return self.async_show_form(
                step_id="activation",
                data_schema=vol.Schema({}),
                errors={"base": "activation_failed"},
            )

    async def _handle_post_authentication(self):
        """Gestisce l'esito positivo di un'autenticazione o ri-autenticazione."""
        if self._reauth_entry:
            _LOGGER.info("Aggiornamento entry esistente con nuovo refresh token.")
            return await config_entry_flow.async_update_reload_and_abort(
                self.hass,
                self._reauth_entry,
                data={
                    CONF_SCAN_INTERVAL: self._reauth_entry.data.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_OPTIONS["15_seconds"]),
                    "refresh_token": self.tado.get_refresh_token(),
                },
                reason="reauth_successful"
            )
        else:
            _LOGGER.info("Autenticazione completata, passando alla configurazione.")
            return await self.async_step_config()

    async def async_step_config(self, user_input=None):
        """Configurazione finale: scelta dello scan_interval."""
        _LOGGER.info("Entrato in async_step_config con user_input=%s", user_input)

        return self.async_create_entry(
            title="Tado Assist",
            data={
                CONF_SCAN_INTERVAL: self.scan_interval,
                "refresh_token": self.tado.get_refresh_token(),
            },
        )

    def _get_data_schema(self, user_input=None):
        return vol.Schema({
            vol.Required(
                "scan_interval",
                default="15_seconds" if not user_input else user_input.get("scan_interval", "15_seconds")
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(SCAN_INTERVAL_OPTIONS.keys()),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="scan_interval"
                )
            )
        })

    async def async_step_reauth(self, entry_data):
        """Gestisce la ri-autenticazione da una configurazione esistente."""
        _LOGGER.info("Esecuzione async_step_reauth con entry_data: %s", entry_data)

        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self.tado = TadoAPI(self.hass, config_entries, refresh_token=entry_data.get("refresh_token"))

        # 🔍 Primo tentativo con token esistente
        status_result = await self.tado.async_initialize(force_new=False)
        status = status_result.get("status")

        if status == "COMPLETED":
            _LOGGER.info("Token esistente ancora valido, aggiorno l'entry.")
            new_token = self.tado.get_refresh_token()
            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={**self._reauth_entry.data, "refresh_token": new_token},
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        if status == "PENDING":
            _LOGGER.info("Token restituisce PENDING, provo un retry rapido prima di forzare nuova autenticazione.")
            await asyncio.sleep(2)  # debounce rapido di 2 secondi
            status_result = await self.tado.async_initialize(force_new=False)
            status = status_result.get("status")

            if status == "COMPLETED":
                _LOGGER.info("Secondo tentativo riuscito, token accettato.")
                new_token = self.tado.get_refresh_token()
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, "refresh_token": new_token},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        # 😬 A questo punto, forziamo davvero il re-auth
        _LOGGER.info("Token non valido, forzo una nuova autenticazione.")
        status_result = await self.tado.async_initialize(force_new=True)
        self._auth_url = status_result.get("auth_url")

        return await self.async_step_reauth_activation()

    async def async_step_reauth_activation(self, user_input=None):
        errors = {}

        try:
            if not user_input:
                _LOGGER.info("Ricarico auth_url per evitare scadenza.")
                status_result = await self.tado.async_initialize(force_new=True)
                self._auth_url = status_result.get("auth_url")

            else:
                _LOGGER.info("Tentativo di attivazione in corso durante la reauth...")

                try:
                    success = await self.tado.async_activate_device()
                    _LOGGER.info("Risultato attivazione: %s", success)

                    # 🔁 AGGIUNGI QUESTO CONTROLLO SUBITO DOPO
                    status_result = await self.tado.async_initialize(force_new=False)
                    status = status_result.get("status")
                    _LOGGER.info("Stato post-attivazione: %s", status_result)

                    if status == "COMPLETED":
                        new_token = self.tado.get_refresh_token()
                        self.hass.config_entries.async_update_entry(
                            self._reauth_entry,
                            data={**self._reauth_entry.data, "refresh_token": new_token},
                        )
                        await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                        return self.async_abort(reason="reauth_successful")

                    self._auth_url = status_result.get("auth_url")
                    errors["base"] = "activation_failed"

                except Exception as e:
                    if "too long" in str(e).lower():
                        _LOGGER.warning("Codice scaduto. Genero nuovo device code.")
                        status_result = await self.tado.async_initialize(force_new=True)
                        self._auth_url = status_result.get("auth_url")
                        errors["base"] = "expired"
                        return self.async_show_form(
                            step_id="reauth_activation",
                            data_schema=vol.Schema({}),
                            description_placeholders={"auth_url": self._auth_url},
                            errors=errors,
                        )
                    raise

        except Exception as e:
            _LOGGER.exception("Errore durante la reauth_activation: %s", e)
            errors["base"] = "activation_failed"

        return self.async_show_form(
            step_id="reauth_activation",
            data_schema=vol.Schema({
                vol.Required("auth_submitted", default=True): bool
            }),
            description_placeholders={"auth_url": self._auth_url},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TadoAssistOptionsFlowHandler(config_entry)


class TadoAssistOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_OPTIONS["15_seconds"])

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required("scan_interval", default="15_seconds"): SelectSelector(
                SelectSelectorConfig(
                    options=list(SCAN_INTERVAL_OPTIONS.keys()),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="scan_interval"
                )
            )
        }))
