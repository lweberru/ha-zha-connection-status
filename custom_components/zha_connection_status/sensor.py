"""Diagnostic sensor for ZHA Connection Status."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import ConnectionStatusMonitor
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diagnostic status sensor."""
    async_add_entities([ConnectionStatusSensor(entry.runtime_data)])


class ConnectionStatusSensor(SensorEntity):
    """Expose the monitored Zigbee-device status as a diagnostic sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_icon = "mdi:zigbee"
    _attr_name = None
    _attr_native_unit_of_measurement = "devices"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "connection_status"

    def __init__(self, monitor: ConnectionStatusMonitor) -> None:
        """Initialize the diagnostic sensor."""
        self.monitor = monitor
        self._attr_unique_id = f"{DOMAIN}_{monitor.entry.entry_id}_status"

    @property
    def native_value(self) -> int:
        """Return the number of currently unavailable devices."""
        return self.monitor.status_summary["unavailable_devices"]

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Return the detailed device availability summary."""
        return self.monitor.status_summary

    async def async_added_to_hass(self) -> None:
        """Subscribe to monitor updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.monitor.async_add_listener(self._async_handle_update))
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_handle_periodic_update,
                timedelta(minutes=1),
            )
        )
        self._async_handle_update()

    @callback
    def _async_handle_periodic_update(self, _now: datetime) -> None:
        """Refresh the diagnostic status even without a device event."""
        self._async_handle_update()

    @callback
    def _async_handle_update(self) -> None:
        """Write the latest summary to Home Assistant."""
        self.schedule_update_ha_state()