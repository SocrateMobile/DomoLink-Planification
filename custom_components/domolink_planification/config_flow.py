"""Configuration Flow et Options Flow pour DomoLink-Planification."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DEFAULT_COUNTRY,
    CONF_DEFAULT_HOLIDAY_MODE,
    CONF_ENABLE_PANEL,
    COUNTRIES,
    COUNTRY_FR,
    DOMAIN,
    HOLIDAY_MODE_ALWAYS,
    HOLIDAY_MODE_EXCLUDE,
    HOLIDAY_MODE_ONLY,
    HOLIDAY_MODE_WEEKEND,
    NAME,
)

HOLIDAY_MODES = {
    HOLIDAY_MODE_ALWAYS: "Actif tous les jours (par défaut)",
    HOLIDAY_MODE_EXCLUDE: "Ne pas exécuter les jours fériés",
    HOLIDAY_MODE_WEEKEND: "Appliquer le comportement Week-end les jours fériés",
    HOLIDAY_MODE_ONLY: "Uniquement les jours fériés",
}


class DomolinkPlanificationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gestionnaire de configuration initiale pour DomoLink-Planification."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape utilisateur lors de l'ajout de l'intégration."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=NAME, data={}, options=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_ENABLE_PANEL, default=True): bool,
                vol.Required(CONF_DEFAULT_COUNTRY, default=COUNTRY_FR): vol.In(COUNTRIES),
                vol.Required(CONF_DEFAULT_HOLIDAY_MODE, default=HOLIDAY_MODE_ALWAYS): vol.In(HOLIDAY_MODES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Retourne le gestionnaire d'options."""
        return DomolinkPlanificationOptionsFlow(config_entry)


class DomolinkPlanificationOptionsFlow(OptionsFlow):
    """Gestionnaire d'options pour activer/désactiver le panneau et changer le pays."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape de modification des options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENABLE_PANEL,
                    default=current_options.get(CONF_ENABLE_PANEL, True),
                ): bool,
                vol.Required(
                    CONF_DEFAULT_COUNTRY,
                    default=current_options.get(CONF_DEFAULT_COUNTRY, COUNTRY_FR),
                ): vol.In(COUNTRIES),
                vol.Required(
                    CONF_DEFAULT_HOLIDAY_MODE,
                    default=current_options.get(CONF_DEFAULT_HOLIDAY_MODE, HOLIDAY_MODE_ALWAYS),
                ): vol.In(HOLIDAY_MODES),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
