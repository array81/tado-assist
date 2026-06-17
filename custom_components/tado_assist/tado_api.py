import logging
import asyncio
from typing import Optional
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import TADO_CLIENT_ID

_LOGGER = logging.getLogger(__name__)

class TadoAuthError(Exception):
    """Eccezione sollevata quando l'autenticazione fallisce in modo irrecuperabile."""
    pass

class TadoApiError(Exception):
    """Eccezione sollevata per errori generici dell'API."""
    pass

class TadoAPI:
    def __init__(self, hass: HomeAssistant, config_entry=None, refresh_token=None):
        self.hass = hass
        self.config_entry = config_entry
        self.refresh_token = refresh_token
        self.access_token = None
        self.home_id = None
        self._device_code = None
        
        # Endpoints Tado CORRETTI
        self._oauth_url = "https://login.tado.com/oauth2"
        self._api_url = "https://my.tado.com/api/v2"
        self._session = async_get_clientsession(self.hass)
        self._lock = asyncio.Lock()

    async def async_initialize(self, force_new=False):
        """Inizializza l'API. Se force_new è True o il refresh_token fallisce, avvia un nuovo login."""
        if self.refresh_token and not force_new:
            try:
                _LOGGER.debug("Tentativo di login con refresh_token salvato...")
                await self._refresh_access_token()
                await self._fetch_me()
                return {"status": "COMPLETED", "auth_url": None}
            except TadoAuthError:
                _LOGGER.warning("Refresh token scaduto o non valido. Necessario nuovo login.")
                self.refresh_token = None
        
        # Se arriviamo qui, dobbiamo avviare il Device Authorization Flow
        return await self._start_device_auth_flow()

    async def _start_device_auth_flow(self):
        """Richiede un device code a Tado e genera l'URL corretto per l'utente."""
        url = f"{self._oauth_url}/device_authorize"
        
        # Tado richiede anche lo scope offline_access per restituire il refresh_token
        payload = {
            "client_id": TADO_CLIENT_ID,
            "scope": "home.user offline_access"
        }
        
        try:
            async with self._session.post(url, data=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise TadoApiError(f"Errore generazione device_code: HTTP {response.status} - {error_text}")
                
                data = await response.json()
                self._device_code = data.get("device_code")
                user_code = data.get("user_code")
                
                # Creiamo l'URL forzando il nostro client_id per evitare errori lato utente
                auth_url = f"https://login.tado.com/oauth2/device?user_code={user_code}&client_id={TADO_CLIENT_ID}"
                
                return {
                    "status": "NOT_STARTED",
                    "auth_url": auth_url
                }
        except Exception as e:
            _LOGGER.error("Impossibile contattare i server Tado per l'auth: %s", e)
            raise TadoApiError("Errore di rete durante l'autenticazione.") from e

    async def async_activate_device(self) -> bool:
        """Chiamato quando l'utente clicca 'INVIA' dopo essersi loggato sul sito Tado."""
        if not self._device_code:
            return False

        url = f"{self._oauth_url}/token"
        payload = {
            "client_id": TADO_CLIENT_ID,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": self._device_code
        }
        
        try:
            async with self._session.post(url, data=payload) as response:
                data = await response.json()
                
                if response.status == 200:
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    await self._fetch_me() # Recupera l'home_id
                    return True
                elif data.get("error") == "authorization_pending":
                    _LOGGER.warning("Autenticazione ancora in attesa di conferma dall'utente.")
                    return False
                else:
                    _LOGGER.error("Errore durante l'attivazione: %s", data)
                    return False
        except Exception as e:
            _LOGGER.error("Errore di rete durante activate_device: %s", e)
            return False

    async def _refresh_access_token(self):
        """Rinnova l'access token usando il refresh token."""
        if not self.refresh_token:
            raise TadoAuthError("Nessun refresh_token disponibile.")

        url = f"{self._oauth_url}/token"
        payload = {
            "client_id": TADO_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        async with self._session.post(url, data=payload) as response:
            if response.status in [400, 401]:
                raise TadoAuthError("Refresh token rifiutato dal server.")
            elif response.status != 200:
                raise TadoApiError(f"Errore HTTP {response.status} durante il refresh.")
            
            data = await response.json()
            self.access_token = data.get("access_token")
            new_refresh = data.get("refresh_token")
            
            if new_refresh and new_refresh != self.refresh_token:
                self.refresh_token = new_refresh
                # Aggiorna il config_entry se esiste
                if self.config_entry and hasattr(self.config_entry, "entry_id"):
                    new_data = {**self.config_entry.data, "refresh_token": self.refresh_token}
                    self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

    async def _request(self, method: str, endpoint: str, json_data=None):
        """Gestisce le chiamate API, rinnovando il token se riceve un 401."""
        async with self._lock:
            if not self.access_token:
                await self._refresh_access_token()

            url = f"{self._api_url}{endpoint}"
            headers = {"Authorization": f"Bearer {self.access_token}"}

            # Primo tentativo
            async with self._session.request(method, url, headers=headers, json=json_data) as response:
                if response.status == 401:
                    _LOGGER.debug("Access token scaduto, tento il rinnovo...")
                    # Fallito? Rinnova il token e riprova
                    await self._refresh_access_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    async with self._session.request(method, url, headers=headers, json=json_data) as retry_resp:
                        if retry_resp.status == 401:
                            raise TadoAuthError("Non autorizzato anche dopo il refresh.")
                        retry_resp.raise_for_status()
                        return await retry_resp.json() if retry_resp.status != 204 else None

                response.raise_for_status()
                return await response.json() if response.status != 204 else None

    async def _fetch_me(self):
        """Recupera l'Home ID dell'utente."""
        data = await self._request("GET", "/me")
        if data and "homes" in data and len(data["homes"]) > 0:
            self.home_id = data["homes"][0]["id"]
        else:
            raise TadoApiError("Impossibile trovare una casa (Home ID) per questo account.")

    def get_refresh_token(self):
        return self.refresh_token

    # --- METODI PER L'INTEGRAZIONE ---

    async def get_home_state(self):
        if not self.home_id: return None
        return await self._request("GET", f"/homes/{self.home_id}/state")

    async def get_mobile_devices(self):
        if not self.home_id: return 0
        devices = await self._request("GET", f"/homes/{self.home_id}/mobileDevices")
        count = 0
        for d in (devices or []):
            # Controlla che il dispositivo sia effettivamente un dizionario valido
            if not isinstance(d, dict):
                continue
            
            # Usiamo "or {}" per prevenire i casi in cui l'API restituisce esplicitamente "null" (None in Python)
            settings = d.get("settings") or {}
            location = d.get("location") or {}
            
            if settings.get("geoTrackingEnabled") and location.get("atHome"):
                count += 1
                
        return count

    async def get_open_window_detected(self):
        if not self.home_id: return []
        zones = await self._request("GET", f"/homes/{self.home_id}/zones")
        open_windows = []
        for zone in (zones or []):
            zone_id = zone["id"]
            state = await self._request("GET", f"/homes/{self.home_id}/zones/{zone_id}/state")
            if state and state.get("openWindow"):
                open_windows.append({"id": zone_id, "name": zone["name"]})
        return open_windows

    async def set_home(self):
        if not self.home_id: return
        await self._request("PUT", f"/homes/{self.home_id}/presenceLock", {"homePresence": "HOME"})

    async def set_away(self):
        if not self.home_id: return
        await self._request("PUT", f"/homes/{self.home_id}/presenceLock", {"homePresence": "AWAY"})

    async def set_open_window(self, zone_id):
        if not self.home_id: return
        # Tado API per attivare la mod. finestra aperta su una zona specifica
        await self._request("POST", f"/homes/{self.home_id}/zones/{zone_id}/state/openWindow/activate")