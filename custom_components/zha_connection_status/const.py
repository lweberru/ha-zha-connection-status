"""Constants for the ZHA Connection Status integration."""

from typing import Final

DOMAIN: Final = "zha_connection_status"

CONF_NOTIFICATION_TARGETS: Final = "notification_targets"
CONF_RECOVERY_TARGETS: Final = "recovery_targets"
CONF_DELAY: Final = "delay"
CONF_LANGUAGE: Final = "language"
CONF_LOW_BATTERY_THRESHOLD: Final = "low_battery_threshold"
CONF_EXCLUDED_DEVICES: Final = "excluded_devices"

DEFAULT_DELAY: Final = 30
DEFAULT_LANGUAGE: Final = "en"
DEFAULT_LOW_BATTERY_THRESHOLD: Final = 20
NOTIFICATION_ID_PREFIX: Final = "zha_connection_status_"

ZIGBEE_PLATFORMS: Final = frozenset({"zha", "hue"})
MONITORED_ENTITY_DOMAINS: Final = frozenset(
	{
		"binary_sensor",
		"climate",
		"cover",
		"fan",
		"humidifier",
		"light",
		"lock",
		"sensor",
		"siren",
		"switch",
		"valve",
		"water_heater",
	}
)
UNAVAILABLE_STATES: Final = frozenset({"unavailable", "unknown"})

MESSAGES: Final = {
	"en": {
		"offline_title": "Zigbee device unavailable",
		"online_title": "Zigbee device available again",
		"offline_persistent": "{device_name} ({entity_id}) is unavailable ({state_name}).{battery_context}",
		"offline_mobile": "{device_name} is offline ({state_name}).{battery_context}",
		"online_mobile": "{device_name} is online again.",
		"battery_level": " Battery level: {battery_level}%.",
		"low_battery": " Low battery ({battery_level}%) may be the cause.",
	},
	"de": {
		"offline_title": "Zigbee-Gerät nicht verfügbar",
		"online_title": "Zigbee-Gerät wieder verfügbar",
		"offline_persistent": "{device_name} ({entity_id}) ist nicht erreichbar ({state_name}).{battery_context}",
		"offline_mobile": "{device_name} ist offline ({state_name}).{battery_context}",
		"online_mobile": "{device_name} ist wieder online.",
		"battery_level": " Batteriestand: {battery_level}%.",
		"low_battery": " Niedriger Batteriestand ({battery_level}%) könnte die Ursache sein.",
	},
}
