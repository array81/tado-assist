import logging
from homeassistant.core import HomeAssistant
from PyTado.interface import Tado

_LOGGER = logging.getLogger(__name__)


class TadoAPI:
    def __init__(self, hass: HomeAssistant, config_entry, refresh_token=None):
        self.hass = hass
        self.config_entry = config_entry
        self._tado = None
        self.auth_url = None
        self.refresh_token = refresh_token
        _LOGGER.info("TadoAPI init - Provided refresh_token: %s", self.refresh_token)

    async def async_initialize(self, force_new=False):
        """Inizializza il client Tado e verifica lo stato di autenticazione."""
        try:
            if self._tado and not force_new:
                _LOGGER.info("TadoAPI - Using existing Tado instance")
            else:
                _LOGGER.info("TadoAPI - Creating a new Tado instance (force_new=%s)", force_new)
                self._tado = await self.hass.async_add_executor_job(
                    lambda: Tado(saved_refresh_token=self.refresh_token)
                )

            status = await self.hass.async_add_executor_job(self._tado.device_activation_status)
            _LOGGER.info("TadoAPI - Activation status: %s", status)

            if status in ["NOT_STARTED", "PENDING"]:
                self.auth_url = await self.hass.async_add_executor_job(self._tado.device_verification_url)
                _LOGGER.info("TadoAPI - Auth URL: %s", self.auth_url)

            await self.check_and_update_token()

            return {
                "status": status,
                "auth_url": self.auth_url,
            }

        except Exception as e:
            _LOGGER.exception("TadoAPI - Error during initialization: %s", e)
            return {
                "status": "error",
                "auth_url": None,
            }

    def get_refresh_token(self):
        return self.refresh_token

    async def check_and_update_token(self):
        """Controlla se il token della libreria è cambiato e lo salva, se necessario."""
        try:
            current_token = await self.hass.async_add_executor_job(self._tado.get_refresh_token)
            if current_token and current_token != self.refresh_token:
                _LOGGER.info("TadoAPI - Token changed. Updating refresh_token.")
                self.refresh_token = current_token
                data = {**self.config_entry.data, "refresh_token": current_token}
                self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        except Exception as e:
            _LOGGER.warning("TadoAPI - Failed to check/update token: %s", e)

    async def async_activate_device(self):
        _LOGGER.info("TadoAPI - Activating your device...")
        await self.hass.async_add_executor_job(self._tado.device_activation)
        status = await self.hass.async_add_executor_job(self._tado.device_activation_status)
        _LOGGER.info("Stato attivazione dopo INVIA: %s", status)

        await self.check_and_update_token()
        return status == "COMPLETED"

    def _is_authenticated(self):
        return self._tado is not None and self.refresh_token is not None

    async def get_home_state(self):
        if not self._is_authenticated():
            _LOGGER.error("TadoAPI - Not authenticated")
            return None
        try:
            state = await self.hass.async_add_executor_job(self._tado.get_home_state)
            await self.check_and_update_token()
            return state
        except Exception as e:
            _LOGGER.error("TadoAPI - Error in get_home_state: %s", e)
            return None

    async def get_mobile_devices(self):
        if not self._is_authenticated():
            _LOGGER.error("TadoAPI - Not authenticated")
            return None
        try:
            devices = await self.hass.async_add_executor_job(self._tado.get_mobile_devices)
            count = sum(
                1 for d in devices
                if d.get("settings", {}).get("geoTrackingEnabled", False)
                and d.get("location", {}).get("atHome")
            )
            await self.check_and_update_token()
            return count
        except Exception as e:
            _LOGGER.error("TadoAPI - Error in get_mobile_devices: %s", e)
            return None

    async def get_open_window_detected(self):
        if not self._is_authenticated():
            _LOGGER.error("TadoAPI - Not authenticated")
            return []
        try:
            zones = await self.hass.async_add_executor_job(self._tado.get_zones)
            open_windows = []
            for zone in zones:
                detection = await self.hass.async_add_executor_job(
                    self._tado.get_open_window_detected, zone["id"]
                )
                if detection.get("openWindowDetected"):
                    open_windows.append({"id": zone["id"], "name": zone["name"]})
            await self.check_and_update_token()
            return open_windows
        except Exception as e:
            _LOGGER.error("TadoAPI - Error in get_open_window_detected: %s", e)
            return []

    async def set_home(self):
        if self._is_authenticated():
            try:
                await self.hass.async_add_executor_job(self._tado.set_home)
                _LOGGER.info("TadoAPI - Home mode set")
                await self.check_and_update_token()
            except Exception as e:
                _LOGGER.error("TadoAPI - Error in set_home: %s", e)

    async def set_away(self):
        if self._is_authenticated():
            try:
                await self.hass.async_add_executor_job(self._tado.set_away)
                _LOGGER.info("TadoAPI - Away mode set")
                await self.check_and_update_token()
            except Exception as e:
                _LOGGER.error("TadoAPI - Error in set_away: %s", e)

    async def set_open_window(self, zone_id):
        if self._is_authenticated():
            try:
                await self.hass.async_add_executor_job(self._tado.set_open_window, zone_id)
                _LOGGER.info("TadoAPI - Open window mode enabled for zone %s", zone_id)
                await self.check_and_update_token()
            except Exception as e:
                _LOGGER.error("TadoAPI - Error in set_open_window: %s", e)
