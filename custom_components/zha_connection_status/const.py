"""Constants for the ZHA Connection Status integration."""

from typing import Final

DOMAIN: Final = "zha_connection_status"

CONF_NOTIFICATION_TARGETS: Final = "notification_targets"
CONF_RECOVERY_TARGETS: Final = "recovery_targets"
CONF_DELAY: Final = "delay"
CONF_LANGUAGE: Final = "language"

DEFAULT_DELAY: Final = 30
DEFAULT_LANGUAGE: Final = "en"
NOTIFICATION_ID_PREFIX: Final = "zha_connection_status_"

UNAVAILABLE_STATES: Final = frozenset({"unavailable", "unknown"})

MESSAGES: Final = {
	"en": {
		"offline_title": "ZHA device unavailable",
		"online_title": "ZHA device available again",
		"offline_persistent": "{device_name} ({entity_id}) is unavailable ({state_name}).",
		"offline_mobile": "{device_name} is offline ({state_name}).",
		"online_mobile": "{device_name} is online again.",
	},
	"de": {
		"offline_title": "ZHA-Gerät nicht verfügbar",
		"online_title": "ZHA-Gerät wieder verfügbar",
		"offline_persistent": "{device_name} ({entity_id}) ist nicht erreichbar ({state_name}).",
		"offline_mobile": "{device_name} ist offline ({state_name}).",
		"online_mobile": "{device_name} ist wieder online.",
	},
}
