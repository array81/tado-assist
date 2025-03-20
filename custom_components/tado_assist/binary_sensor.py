import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    # Initialize the binary sensors for Tado Assist
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        TadoHomeStateSensor(entry, coordinator),
        TadoOpenWindowSensor(entry, coordinator)
    ], True)

class TadoBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):  
    # Base class for all Tado binary sensors
    def __init__(self, entry, coordinator, translation_key, unique_id):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{unique_id}"
        self._attr_translation_key = translation_key
        
    @property
    def device_info(self) -> DeviceInfo:
        # Provide device details for Home Assistant
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Tado Assist",
            manufacturer="Tado",
            model="API Integration",
            entry_type="service",
        )

class TadoHomeStateSensor(TadoBaseBinarySensor):
    # Binary sensor to represent the Tado home state
    def __init__(self, entry, coordinator):
        super().__init__(entry, coordinator, "tado_binary_home_state", "home_state")

    @property
    def is_on(self):
        # Determine if the home state is set to HOME
        if not self.coordinator.data:
            return None
        home_state = self.coordinator.data.get("home_state", {})
        return home_state.get("presence") == "HOME"

    @property
    def extra_state_attributes(self):
        # Provide additional attributes such as the number of mobile devices at home
        mobile_devices = self.coordinator.data.get("mobile_devices", 0)
        return {"devices_at_home": mobile_devices}

class TadoOpenWindowSensor(TadoBaseBinarySensor):
    # Binary sensor to detect open windows
    def __init__(self, entry, coordinator):
        super().__init__(entry, coordinator, "tado_binary_open_windows", "open_window")

    @property
    def is_on(self):
        # Determine if any windows are detected as open
        if not self.coordinator.data:
            return None
        open_window_zone_ids = self.coordinator.data.get("open_window_zone_ids", [])
        return len(open_window_zone_ids) > 0

    @property
    def extra_state_attributes(self):
        # Provide additional attributes such as the list of zones with open windows
        open_window_zone_names = self.coordinator.data.get("open_window_zone_names", [])
        if isinstance(open_window_zone_names, list) and open_window_zone_names:
            return {"windows_open_zones": open_window_zone_names}
        else:
            return {}

