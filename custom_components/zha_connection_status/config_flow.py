"""Config flow for ZHA Connection Status."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers import selector

from .const import (
    CONF_DELAY,
    CONF_EXCLUDED_DEVICES,
    CONF_LANGUAGE,
    CONF_LOW_BATTERY_THRESHOLD,
    CONF_NOTIFICATION_TARGETS,
    CONF_RECOVERY_TARGETS,
    DEFAULT_DELAY,
    DEFAULT_LANGUAGE,
    DEFAULT_LOW_BATTERY_THRESHOLD,
    DOMAIN,
)


class ZHAConnectionStatusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZHA Connection Status."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="ZHA Connection Status", data={}, options=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=self._schema(self.hass)
        )

    @staticmethod
    def _schema(hass, defaults: dict | None = None) -> vol.Schema:
        """Build the configuration schema from available notify services."""
        defaults = defaults or {}
        notify_services = sorted(hass.services.async_services().get("notify", {}))
        return vol.Schema(
            {
                vol.Required(
                    CONF_NOTIFICATION_TARGETS,
                    default=defaults.get(CONF_NOTIFICATION_TARGETS, []),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_services, multiple=True
                    )
                ),
                vol.Optional(
                    CONF_RECOVERY_TARGETS,
                    default=defaults.get(CONF_RECOVERY_TARGETS, []),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_services, multiple=True
                    )
                ),
                vol.Optional(CONF_DELAY, default=defaults.get(CONF_DELAY, DEFAULT_DELAY)): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=3600)
                ),
                vol.Optional(
                    CONF_LANGUAGE,
                    default=defaults.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["en", "de"])
                ),
                vol.Optional(
                    CONF_LOW_BATTERY_THRESHOLD,
                    default=defaults.get(
                        CONF_LOW_BATTERY_THRESHOLD, DEFAULT_LOW_BATTERY_THRESHOLD
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                vol.Optional(
                    CONF_EXCLUDED_DEVICES,
                    default=defaults.get(CONF_EXCLUDED_DEVICES, []),
                ): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(multiple=True)
                ),
            }
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow for this handler."""
        return OptionsFlow()


class OptionsFlow(OptionsFlowWithReload):
    """Handle options for ZHA Connection Status."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=ZHAConnectionStatusConfigFlow._schema(
                self.hass, self.config_entry.options
            ),
        )
