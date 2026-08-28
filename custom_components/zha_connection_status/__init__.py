"""ZHA Connection Status integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, SensorDeviceClass
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later

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
    NOTIFICATION_ID_PREFIX,
    UNAVAILABLE_STATES,
    ZIGBEE_PLATFORMS,
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZHA Connection Status from a config entry."""
    monitor = ConnectionStatusMonitor(hass, entry)
    entry.runtime_data = monitor
    entry.async_on_unload(monitor.async_start())
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    return True


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
        language = entry.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        self.messages = MESSAGES.get(language, MESSAGES[DEFAULT_LANGUAGE])

    @callback
    def async_start(self) -> Callable[[], None]:
        """Start monitoring state changes."""
        unsubscribe = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._async_handle_state_change
        )
        self._async_restore_device_states()

        @callback
        def async_stop() -> None:
            """Stop monitoring and cancel delayed checks."""
            unsubscribe()
            for cancel_check in self.pending_checks.values():
                cancel_check()
            self.pending_checks.clear()

        return async_stop

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
                self.hass.services.async_call(
                    "persistent_notification",
                    "dismiss",
                    {"notification_id": notification_id},
                )

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

        was_unavailable = old_state is not None and old_state.state in UNAVAILABLE_STATES
        is_unavailable = new_state.state in UNAVAILABLE_STATES

        if is_unavailable and not was_unavailable:
            self._async_schedule_offline_check(device_id)
        elif was_unavailable and not is_unavailable:
            self._async_handle_recovery(device_id, entity_id, new_state)

    @callback
    def _async_schedule_offline_check(self, device_id: str) -> None:
        """Wait before announcing a device as unavailable."""
        if device_id in self.pending_checks or device_id in self.offline_devices:
            return

        delay = self.entry.options.get(CONF_DELAY, DEFAULT_DELAY)
        self.pending_checks[device_id] = async_call_later(
            self.hass,
            delay,
            lambda _now: self._async_confirm_offline(device_id),
        )

    @callback
    def _async_confirm_offline(self, device_id: str) -> None:
        """Create notifications if the device is still unavailable."""
        self.pending_checks.pop(device_id, None)
        entity_id = self._async_unavailable_entity_id(device_id)
        if not entity_id:
            return

        device_name = self._device_name(device_id, entity_id)
        state = self.hass.states.get(entity_id)
        state_name = state.state if state else "unavailable"
        battery_context = self._battery_context(device_id)
        self.offline_devices.add(device_id)

        if self.hass.states.get(
            f"persistent_notification.{self._notification_id(device_id)}"
        ):
            return

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
        self._async_send_mobile_notifications(
            self.entry.options.get(CONF_NOTIFICATION_TARGETS, []),
            self.messages["offline_title"],
            self.messages["offline_mobile"].format(
                device_name=device_name,
                state_name=state_name,
                battery_context=battery_context,
            ),
        )

    @callback
    def _async_handle_recovery(
        self, device_id: str, entity_id: str, new_state: State
    ) -> None:
        """Dismiss notifications after an unavailable device recovers."""
        cancel_check = self.pending_checks.pop(device_id, None)
        if cancel_check:
            cancel_check()

        if self._async_unavailable_entity_id(device_id):
            return

        notification_state = self.hass.states.get(
            f"persistent_notification.{self._notification_id(device_id)}"
        )
        if device_id not in self.offline_devices and notification_state is None:
            return

        self.offline_devices.discard(device_id)
        device_name = self._device_name(device_id, entity_id)
        self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": self._notification_id(device_id)},
        )
        self._async_send_mobile_notifications(
            self.entry.options.get(CONF_RECOVERY_TARGETS, []),
            self.messages["online_title"],
            self.messages["online_mobile"].format(device_name=device_name),
        )

    @callback
    def _async_unavailable_entity_id(self, device_id: str) -> str | None:
        """Return one currently unavailable monitored Zigbee entity."""
        for registry_entry in er.async_entries_for_device(self.entity_registry, device_id):
            if registry_entry.platform not in ZIGBEE_PLATFORMS:
                continue
            state = self.hass.states.get(registry_entry.entity_id)
            if state and state.state in UNAVAILABLE_STATES:
                return registry_entry.entity_id
        return None

    def _battery_context(self, device_id: str) -> str:
        """Return the latest battery information for a battery-powered device."""
        for registry_entry in er.async_entries_for_device(self.entity_registry, device_id):
            if registry_entry.device_class != SensorDeviceClass.BATTERY:
                continue

            state = self.hass.states.get(registry_entry.entity_id)
            if state is None:
                continue

            try:
                battery_level = float(state.state)
            except ValueError:
                continue

            if not 0 <= battery_level <= 100:
                continue

            battery_level_text = f"{battery_level:g}"
            threshold = self.entry.options.get(
                CONF_LOW_BATTERY_THRESHOLD, DEFAULT_LOW_BATTERY_THRESHOLD
            )
            message_key = "low_battery" if battery_level <= threshold else "battery_level"
            return self.messages[message_key].format(battery_level=battery_level_text)

        return ""

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
                self.hass.services.async_call(
                    "notify", target, {"title": title, "message": message}
                )
