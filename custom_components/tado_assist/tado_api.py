import logging
import asyncio
from PyTado.interface import Tado  # Import Tado API client from the PyTado package

_LOGGER = logging.getLogger(__name__)

class TadoAPI:

    def __init__(self, hass, username: str, password: str):
        # Initialize the Tado API client asynchronously
        self.hass = hass
        self.username = username
        self.password = password
        self._tado = None

    def get_home_state(self):
        # Fetch the home state data from Tado
        _LOGGER.info("TadoAPI: get_home_state() called")
        
        if not self._tado:  # Check if the Tado client is initialized
            _LOGGER.error("TadoAPI: API not initialized!")
            return None

        try:
            data = self._tado.get_home_state()  # Synchronously fetch the home state data
            _LOGGER.debug("TadoAPI: get_home_state(): %s", data)
            return data
        except Exception as e:
            _LOGGER.error("TadoAPI: Error get_home_state - %s", e)
            return None

    def get_mobile_devices(self):
        # Fetch mobile device data from Tado
        _LOGGER.info("TadoAPI: get_mobile_devices() called")
        
        if not self._tado:  # Check if the Tado client is initialized
            _LOGGER.error("TadoAPI: API not initialized!")
            return None

        try:
            devicesHome = []  # Initialize an empty list to store mobile devices at home

            for mobileDevice in self._tado.get_mobile_devices():
                settings = mobileDevice.get("settings", {})
                geo_tracking = settings.get("geoTrackingEnabled", False)  # Check if geo tracking is enabled
                location = mobileDevice.get("location", None)  # Get the location data of the mobile device
                
                if geo_tracking and location and location.get("atHome"):  # Check if device is geo-tracked and at home
                    devicesHome.append(mobileDevice["name"])

            _LOGGER.debug("TadoAPI: get_mobile_devices(): %s", devicesHome)  # Log the list of devices at home
            return len(devicesHome)

        except Exception as e:
            _LOGGER.error("TadoAPI: Error get_mobile_devices - %s", e)
            return None
            
    def get_open_window_detected(self):
        # Returns the zones with open windows detected
        _LOGGER.info("TadoAPI: get_open_window_detected() called")
        
        if not self._tado:  # Check if the Tado client is initialized
            _LOGGER.error("TadoAPI: API not initialized!")
            return []

        try:
            zones = self._tado.get_zones()  # Retrieve all the zones from Tado
            open_window_zones = []

            for zone in zones:  # Loop through each zone
                zone_id = zone['id']  # Get the zone ID
                
                if (self._tado.get_open_window_detected(zone_id)["openWindowDetected"] == True):  # Check if open window is detected
                    _LOGGER.info("TadoAPI: Open window detected in %s area", zone['name'])  # Log the zone name
                    open_window_zones.append({"id": zone_id, "name": zone["name"]})  # Add zone ID and name to the list

            return open_window_zones

        except Exception as e:
            _LOGGER.error("TadoAPI: Error get_open_window_detected - %s", e)
            return []
            
    def set_home(self):
        # Set the mode to 'home'
        _LOGGER.info("TadoAPI: set_home() called")
    
        if not self._tado:  # Check if the Tado client is initialized
            _LOGGER.error("TadoAPI: API not initialized!")
            return None
            
        try:
            self._tado.set_home()  # Set the mode to 'home' using Tado client
            _LOGGER.info("TadoAPI: Home mode set")
        except Exception as e:
            _LOGGER.error("TadoAPI: Error set_home - %s", e)
            return None
            
    def set_away(self):
        # Set the mode to 'away'
        _LOGGER.info("TadoAPI: set_away() called")
        
        if not self._tado:  # Check if the Tado client is initialized
            _LOGGER.error("TadoAPI: API not initialized!")
            return None
            
        try:
            self._tado.set_away()  # Set the mode to 'away' using Tado client
            _LOGGER.info("TadoAPI: Away mode set")
        except Exception as e:
            _LOGGER.error("TadoAPI: Error set_away - %s", e)
            return None
            
    def set_open_window(self, zone_id):
        # Set the open window mode for a specific zone
        _LOGGER.info("TadoAPI: set_open_window() called")
        
        if not self._tado:  # Check if the Tado client is initialized
            _LOGGER.error("TadoAPI: API not initialized!")
            return  # Return if not initialized

        try:
            self._tado.set_open_window(zone_id)  # Set the open window mode for the specified zone
            _LOGGER.info("TadoAPI: Open window set to zone %s", zone_id)
        except Exception as e:
            _LOGGER.error("TadoAPI: Error set_open_window - %s", e)

    async def async_login(self):
        # Login to Tado with retry mechanism in case of error 429
        for attempt in range(5):  # Retry up to 5 times
            try:
                self._tado = await self.hass.async_add_executor_job(Tado, self.username, self.password)  # Login asynchronously
                _LOGGER.info("TadoAPI: Tado server login failed!")  # Log a success message if login succeeds
                return
            except TadoException as e:
                if "429" in str(e):  # If it's a rate limit error (HTTP 429), retry after a delay
                    wait_time = (attempt + 1) * 10  # Implement an exponential backoff strategy
                    _LOGGER.warning(f"Error 429, try again in {wait_time} seconds...")  # Warn the user about the delay
                    await asyncio.sleep(wait_time)  # Wait before retrying
                else:
                    _LOGGER.error(f"TadoAPI: Login error: {e}")  # Log any other login errors
                    break  # Exit the loop if the error is not 429
        else:
            _LOGGER.error("TadoAPI: Too many requests, unable to log in after 5 attempts.")  # Log if login fails after 5 attempts
