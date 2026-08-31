"""ZHA Connection Status integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.zha.helpers import get_zha_gateway_proxy
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    CONF_DELAY,
    CONF_LANGUAGE,
    CONF_LOW_BATTERY_THRESHOLD,
    CONF_NOTIFICATION_TARGETS,
    CONF_RECOVERY_TARGETS,
    DEFAULT_DELAY,
    DEFAULT_LANGUAGE,
    DEFAULT_LOW_BATTERY_THRESHOLD,
    DOMAIN,
    MESSAGES,
    MONITORED_ENTITY_DOMAINS,
    NOTIFICATION_ID_PREFIX,
    UNAVAILABLE_STATES,
    ZIGBEE_PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZHA Connection Status from a config entry."""
    monitor = ConnectionStatusMonitor(hass, entry)
    entry.runtime_data = monitor
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    entry.async_on_unload(monitor.async_start())
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate version 1 configuration data to options."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            data={},
            options={**entry.data, **entry.options},
            version=2,
        )

    return True


class ConnectionStatusMonitor:
    """Monitor ZHA entity availability and manage notifications."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the monitor."""
        self.hass = hass
        self.entry = entry
        self.entity_registry = er.async_get(hass)
        self.device_registry = dr.async_get(hass)
        self.pending_checks: dict[str, Callable[[], None]] = {}
        self.offline_devices: set[str] = set()
        self._listeners: set[Callable[[], None]] = set()
        language = entry.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        self.messages = MESSAGES.get(language, MESSAGES[DEFAULT_LANGUAGE])

    @callback
    def async_start(self) -> Callable[[], None]:
        """Start monitoring state changes."""
        unsubscribe = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._async_handle_state_change
        )
        unsubscribe_periodic_update = async_track_time_interval(
            self.hass,
            self._async_handle_periodic_update,
            timedelta(minutes=1),
        )
        self._async_restore_device_states()

        @callback
        def async_stop() -> None:
            """Stop monitoring and cancel delayed checks."""
            unsubscribe()
            unsubscribe_periodic_update()
            for cancel_check in self.pending_checks.values():
                cancel_check()
            self.pending_checks.clear()

        return async_stop

    @callback
    def _async_handle_periodic_update(self, _now: datetime) -> None:
        """Reconcile device availability if an event was missed."""
        self._async_restore_device_states()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener that receives availability summary updates."""
        self._listeners.add(listener)

        @callback
        def async_remove_listener() -> None:
            self._listeners.discard(listener)

        return async_remove_listener

    @callback
    def _async_notify_listeners(self) -> None:
        """Notify status entities about a changed device state."""
        for listener in self._listeners:
            listener()

    @property
    def status_summary(self) -> dict[str, int]:
        """Return the current monitored-device availability summary."""
        device_platforms: dict[str, set[str]] = {}
        for registry_entry in self.entity_registry.entities.values():
            if (
                registry_entry.platform in ZIGBEE_PLATFORMS
                and registry_entry.device_id
            ):
                device_platforms.setdefault(registry_entry.device_id, set()).add(
                    registry_entry.platform
                )

        device_ids = device_platforms.keys()
        threshold = self.entry.options.get(
            CONF_LOW_BATTERY_THRESHOLD, DEFAULT_LOW_BATTERY_THRESHOLD
        )
        battery_levels = {
            device_id: self._battery_level(device_id) for device_id in device_ids
        }
        unavailable_devices = {
            device_id: self._async_unavailable_entity_id(device_id)
            for device_id in device_ids
        }
        summary = {
            "monitored_devices": len(device_platforms),
            "zha_devices": sum("zha" in platforms for platforms in device_platforms.values()),
            "hue_devices": sum("hue" in platforms for platforms in device_platforms.values()),
            "unavailable_devices": sum(
                entity_id is not None for entity_id in unavailable_devices.values()
            ),
            "battery_devices": sum(level is not None for level in battery_levels.values()),
            "low_battery_devices": sum(
                level is not None and level <= threshold
                for level in battery_levels.values()
            ),
        }
        return summary

    @callback
    def _async_restore_device_states(self) -> None:
        """Restore monitoring state and reconcile notifications after a restart."""
        device_ids = {
            registry_entry.device_id
            for registry_entry in self.entity_registry.entities.values()
            if registry_entry.platform in ZIGBEE_PLATFORMS and registry_entry.device_id
        }

        for device_id in device_ids:
            unavailable_entity_id = self._async_unavailable_entity_id(device_id)
            notification_id = self._notification_id(device_id)
            notification_state = self.hass.states.get(
                f"persistent_notification.{notification_id}"
            )

            if unavailable_entity_id:
                if notification_state:
                    self.offline_devices.add(device_id)
                else:
                    self._async_schedule_offline_check(device_id)
            elif notification_state:
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "persistent_notification",
                        "dismiss",
                        {"notification_id": notification_id},
                    )
                )

        self._async_notify_listeners()

    @callback
    def _async_handle_state_change(self, event: Event) -> None:
        """Handle a monitored Zigbee entity availability transition."""
        entity_id = event.data.get("entity_id")
        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data.get("new_state")

        if not entity_id or not new_state:
            return

        registry_entry = self.entity_registry.async_get(entity_id)
        if not registry_entry or registry_entry.platform not in ZIGBEE_PLATFORMS:
            return

        device_id = registry_entry.device_id
        if not device_id:
            return

        if not self._is_monitored_entity(registry_entry.entity_id):
            self._async_notify_listeners()
            return

        is_unavailable = new_state.state in UNAVAILABLE_STATES

        if is_unavailable:
            self._async_schedule_offline_check(device_id)
        elif old_state is not None and old_state.state in UNAVAILABLE_STATES:
            self._async_handle_recovery(device_id, entity_id, new_state)

        self._async_notify_listeners()

    @callback
    def _async_schedule_offline_check(self, device_id: str) -> None:
        """Wait before announcing a device as unavailable."""
        if device_id in self.pending_checks or device_id in self.offline_devices:
            _LOGGER.debug(
                "Offline check not scheduled for %s: pending=%s, offline=%s",
                device_id,
                device_id in self.pending_checks,
                device_id in self.offline_devices,
            )
            return

        delay = self.entry.options.get(CONF_DELAY, DEFAULT_DELAY)
        _LOGGER.debug("Scheduling offline check for %s in %s seconds", device_id, delay)
        self.pending_checks[device_id] = async_call_later(
            self.hass,
            delay,
            self._async_confirm_offline_callback(device_id),
        )
        self._async_notify_listeners()

    def _async_confirm_offline_callback(
        self, device_id: str
    ) -> Callable[[datetime], None]:
        """Create an event-loop-safe delayed offline callback."""

        @callback
        def async_confirm_offline(_now: datetime) -> None:
            self._async_confirm_offline(device_id)

        return async_confirm_offline

    @callback
    def _async_confirm_offline(self, device_id: str) -> None:
        """Create notifications if the device is still unavailable."""
        self.pending_checks.pop(device_id, None)
        entity_id = self._async_unavailable_entity_id(device_id)
        if not entity_id:
            _LOGGER.debug("Offline check for %s found the device available", device_id)
            self._async_notify_listeners()
            return

        device_name = self._device_name(device_id, entity_id)
        state = self.hass.states.get(entity_id)
        state_name = state.state if state else "unavailable"
        battery_context = self._battery_context(device_id)
        self.offline_devices.add(device_id)

        if self.hass.states.get(
            f"persistent_notification.{self._notification_id(device_id)}"
        ):
            _LOGGER.debug("Offline notification for %s already exists", device_id)
            self._async_notify_listeners()
            return

        _LOGGER.debug(
            "Creating offline notification for %s (%s)", device_id, device_name
        )
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": self.messages["offline_title"],
                    "message": self.messages["offline_persistent"].format(
                        device_name=device_name,
                        entity_id=entity_id,
                        state_name=state_name,
                        battery_context=battery_context,
                    ),
                    "notification_id": self._notification_id(device_id),
                },
            )
        )
        self._async_send_mobile_notifications(
            self.entry.options.get(CONF_NOTIFICATION_TARGETS, []),
            self.messages["offline_title"],
            self.messages["offline_mobile"].format(
                device_name=device_name,
                state_name=state_name,
                battery_context=battery_context,
            ),
        )
        self._async_notify_listeners()

    @callback
    def _async_handle_recovery(
        self, device_id: str, entity_id: str, new_state: State
    ) -> None:
        """Dismiss notifications after an unavailable device recovers."""
        cancel_check = self.pending_checks.pop(device_id, None)
        if cancel_check:
            cancel_check()

        if self._async_unavailable_entity_id(device_id):
            self._async_notify_listeners()
            return

        notification_state = self.hass.states.get(
            f"persistent_notification.{self._notification_id(device_id)}"
        )
        if device_id not in self.offline_devices and notification_state is None:
            self._async_notify_listeners()
            return

        self.offline_devices.discard(device_id)
        device_name = self._device_name(device_id, entity_id)
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": self._notification_id(device_id)},
            )
        )
        self._async_send_mobile_notifications(
            self.entry.options.get(CONF_RECOVERY_TARGETS, []),
            self.messages["online_title"],
            self.messages["online_mobile"].format(device_name=device_name),
        )
        self._async_notify_listeners()

    @callback
    def _async_unavailable_entity_id(self, device_id: str) -> str | None:
        """Return an entity only when all relevant entities are unavailable."""
        registry_entries = er.async_entries_for_device(self.entity_registry, device_id)
        relevant_entities = [
            registry_entry.entity_id for registry_entry in registry_entries
            if (
                registry_entry.platform in ZIGBEE_PLATFORMS
                and self._is_monitored_entity(registry_entry.entity_id)
            )
        ]
        if not relevant_entities:
            return None

        if any(entry.platform == "zha" for entry in registry_entries):
            zha_available = self._zha_device_available(device_id)
            if zha_available is not None:
                return None if zha_available else relevant_entities[0]

        if any(entry.platform == "hue" for entry in registry_entries):
            hue_available = self._hue_device_available(device_id)
            return None if hue_available is not False else relevant_entities[0]

        unavailable_entities = [
            entity_id
            for entity_id in relevant_entities
            if (state := self.hass.states.get(entity_id))
            and state.state in UNAVAILABLE_STATES
        ]
        if len(unavailable_entities) != len(relevant_entities):
            return None

        return unavailable_entities[0]

    @callback
    def _zha_device_available(self, device_id: str) -> bool | None:
        """Return ZHA's authoritative availability for a registered device."""
        zha_gateway_proxy = get_zha_gateway_proxy(self.hass)
        for device_proxy in zha_gateway_proxy.device_proxies.values():
            device_info = device_proxy.zha_device_info
            if device_info["device_reg_id"] == device_id:
                return device_info["available"]

        return None

    @callback
    def _hue_device_available(self, device_id: str) -> bool | None:
        """Return Hue's Zigbee connectivity status for a registered device."""
        device = self.device_registry.async_get(device_id)
        if device is None:
            return None

        hue_device_ids = {
            identifier for domain, identifier in device.identifiers if domain == "hue"
        }
        if not hue_device_ids:
            return None

        for config_entry_id in device.config_entries:
            config_entry = self.hass.config_entries.async_get_entry(config_entry_id)
            if config_entry is None or config_entry.domain != "hue":
                continue

            bridge = config_entry.runtime_data
            if bridge is None:
                continue

            for hue_device_id in hue_device_ids:
                try:
                    connectivity = bridge.api.devices.get_zigbee_connectivity(
                        hue_device_id
                    )
                except KeyError:
                    _LOGGER.debug(
                        "Hue device %s has no current connectivity record",
                        hue_device_id,
                    )
                    continue
                if connectivity is not None:
                    is_available = connectivity.status.value not in {
                        "disconnected",
                        "connectivity_issue",
                    }
                    _LOGGER.debug(
                        "Hue device %s connectivity is %s (available: %s)",
                        hue_device_id,
                        connectivity.status.value,
                        is_available,
                    )
                    return is_available

        return None

    @staticmethod
    def _is_monitored_entity(entity_id: str) -> bool:
        """Return whether an entity reports device availability meaningfully."""
        return entity_id.partition(".")[0] in MONITORED_ENTITY_DOMAINS

    def _battery_context(self, device_id: str) -> str:
        """Return the latest battery information for a battery-powered device."""
        battery_level = self._battery_level(device_id)
        if battery_level is None:
            return ""

        battery_level_text = f"{battery_level:g}"
        threshold = self.entry.options.get(
            CONF_LOW_BATTERY_THRESHOLD, DEFAULT_LOW_BATTERY_THRESHOLD
        )
        message_key = "low_battery" if battery_level <= threshold else "battery_level"
        return self.messages[message_key].format(battery_level=battery_level_text)

    def _battery_level(self, device_id: str) -> float | None:
        """Return the latest reported battery level for a device."""
        for registry_entry in er.async_entries_for_device(
            self.entity_registry, device_id
        ):
            state = self.hass.states.get(registry_entry.entity_id)
            if (
                state is None
                or state.attributes.get("device_class") != SensorDeviceClass.BATTERY
            ):
                continue

            try:
                battery_level = float(state.state)
            except ValueError:
                continue

            if not 0 <= battery_level <= 100:
                continue

            return battery_level

        return None

    def _device_name(self, device_id: str, entity_id: str) -> str:
        """Return the device name, falling back to the entity name."""
        device = self.device_registry.async_get(device_id)
        if device:
            return device.name_by_user or device.name
        state = self.hass.states.get(entity_id)
        return state.name if state else entity_id

    @staticmethod
    def _notification_id(device_id: str) -> str:
        """Create a persistent, unique notification identifier."""
        return f"{NOTIFICATION_ID_PREFIX}{device_id}"

    def _async_send_mobile_notifications(
        self, targets: list[str], title: str, message: str
    ) -> None:
        """Send a notification through each configured notify service."""
        for target in targets:
            if self.hass.services.has_service("notify", target):
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "notify", target, {"title": title, "message": message}
                    )
                )
