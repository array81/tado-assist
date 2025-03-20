import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    # Set up the switches for Tado Assist
    coordinator = hass.data[DOMAIN][entry.entry_id]
    tado = hass.data[DOMAIN]["tado"]

    switches = [
        TadoEnabledAssistSwitch(hass, entry, coordinator),
        TadoGeoreferencingSwitch(hass, entry, coordinator, tado),
        TadoWindowControlSwitch(hass, entry, coordinator, tado)
    ]

    async_add_entities(switches, True)
    hass.data[DOMAIN]["switch_entities"] = switches

class TadoBaseSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):  
    # Base class for Tado switches
    def __init__(self, hass, entry, coordinator, translation_key, unique_id):
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{unique_id}"
        self._attr_is_on = None
        self._attr_translation_key = translation_key

    async def async_added_to_hass(self):
        # Restore previous state when added to Home Assistant
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in ["on", "off"]:
            self._attr_is_on = last_state.state == "on"
        else:
            self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        # Return device information for the Tado Assist device
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Tado Assist",
            manufacturer="Tado",
            model="API Integration",
            entry_type="service",
        )

class TadoEnabledAssistSwitch(TadoBaseSwitch):
    # Switch to enable or disable Tado Assist
    def __init__(self, hass, entry, coordinator):
        super().__init__(hass, entry, coordinator, "tado_switch_enabled_assist", "tado_enabled_assist")

    @property
    def is_on(self):
        return self._attr_is_on

    async def async_turn_on(self, **kwargs):
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._attr_is_on = False
        self.async_write_ha_state()

class TadoGeoreferencingSwitch(TadoBaseSwitch):
    # Switch to enable or disable Tado's georeferencing mode
    def __init__(self, hass, entry, coordinator, tado):
        super().__init__(hass, entry, coordinator, "tado_switch_georeferencing", "georeferencing_switch")
        self.tado = tado

    @property
    def is_on(self):
        return self._attr_is_on if self._attr_is_on is not None else False

    async def async_turn_on(self, **kwargs):
        self._attr_is_on = True
        self.hass.data[DOMAIN]["last_data"]["tado_georeferencing_status"] = True
        self.async_write_ha_state()
        await self.async_check_and_set_home_or_away()

    async def async_turn_off(self, **kwargs):
        self._attr_is_on = False
        self.hass.data[DOMAIN]["last_data"]["tado_georeferencing_status"] = False
        self.async_write_ha_state()

    async def async_check_and_set_home_or_away(self):
        # Update home/away status based on georeferencing data
        if self._attr_is_on:
            home_state = self.coordinator.data.get("home_state", {})
            devices_at_home = self.coordinator.data.get("mobile_devices", 0)
            if home_state.get("presence") == "HOME" and devices_at_home == 0:
                _LOGGER.info("No mobile devices at home, setting AWAY mode...")
                await self.hass.async_add_executor_job(self.tado.set_away)
            elif home_state.get("presence") == "AWAY" and devices_at_home > 0:
                _LOGGER.info("Mobile devices detected at home, setting HOME mode...")
                await self.hass.async_add_executor_job(self.tado.set_home)

class TadoWindowControlSwitch(TadoBaseSwitch):
    # Switch to enable or disable automatic window control
    def __init__(self, hass, entry, coordinator, tado):
        super().__init__(hass, entry, coordinator, "tado_switch_auto_window_control", "window_control_switch")
        self.tado = tado

    @property
    def is_on(self):
        return self._attr_is_on if self._attr_is_on is not None else False

    async def async_turn_on(self, **kwargs):
        self._attr_is_on = True
        self.async_write_ha_state()
        await self.async_check_and_pause_thermostat()

    async def async_turn_off(self, **kwargs):
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_check_and_pause_thermostat(self):
        # Pause heating in areas where open windows are detected
        if self._attr_is_on:
            open_window_zone_ids = self.coordinator.data.get("open_window_zone_ids", [])
            for zone_id in open_window_zone_ids:
                _LOGGER.info("Activating temporary heating suspension for zone %s", zone_id)
                await self.hass.async_add_executor_job(self.tado.set_open_window, zone_id)
