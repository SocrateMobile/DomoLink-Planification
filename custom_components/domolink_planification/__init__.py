"""Intégration DomoLink-Planification pour Home Assistant."""

from __future__ import annotations

import logging
import os
from typing import Any

from aiohttp import web

from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ENABLE_PANEL,
    DOMAIN,
    FRONTEND_FILE_NAME,
    FRONTEND_URL_PATH,
    NAME,
    PANEL_ICON,
    PANEL_NAME,
    PANEL_TITLE,
    PANEL_URL_PATH,
    VERSION,
)
from .coordinator import DomolinkPlanificationCoordinator
from .storage import PlanificationStorage

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "sensor", "button"]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Configuration globale du composant."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise DomoLink-Planification depuis une ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    storage = PlanificationStorage(hass)
    coordinator = DomolinkPlanificationCoordinator(hass, storage)
    await coordinator.async_init()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "storage": storage,
    }

    # 1. Enregistrer les fichiers statiques frontend
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    if os.path.exists(frontend_dir):
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig
            await hass.http.async_register_static_paths([
                StaticPathConfig(FRONTEND_URL_PATH, frontend_dir, cache_headers=False)
            ])
        elif hasattr(hass.http, "register_static_path"):
            try:
                hass.http.register_static_path(FRONTEND_URL_PATH, frontend_dir, cache_headers=False)
            except Exception as err:
                _LOGGER.debug("Erreur register_static_path: %s", err)

    # 2. Gestion du panneau latéral (selon l'option utilisateur)
    enable_panel = entry.options.get(CONF_ENABLE_PANEL, True)
    if enable_panel:
        _async_register_panel(hass)
    else:
        _async_remove_panel(hass)

    # 3. Enregistrer les vues API HTTP pour le panneau frontend
    hass.http.register_view(DomolinkPlanificationApiView(coordinator))

    # 4. Enregistrer les plateformes d'entités
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 5. Enregistrer les services Home Assistant
    async def handle_trigger(call: ServiceCall) -> None:
        """Déclenche manuellement une planification."""
        schedule_id = call.data.get("schedule_id")
        if schedule_id:
            await coordinator.async_trigger_now(schedule_id)

    async def handle_solar_refresh(call: ServiceCall) -> None:
        """Force la réévaluation des volets solaires."""
        from homeassistant.util import dt as dt_util
        await coordinator._evaluate_solar_shading_rules(dt_util.now())
        coordinator.async_set_updated_data(await coordinator._async_update_data())

    async def handle_set_enabled(call: ServiceCall) -> None:
        """Active ou désactive une règle."""
        schedule_id = call.data.get("schedule_id")
        enabled = call.data.get("enabled", True)
        if schedule_id:
            sched = coordinator.storage.get_schedule(schedule_id)
            if sched:
                sched["enabled"] = enabled
                await coordinator.storage.async_save_schedule(schedule_id, sched)
                coordinator.async_set_updated_data(await coordinator._async_update_data())

    hass.services.async_register(DOMAIN, "trigger_schedule", handle_trigger)
    hass.services.async_register(DOMAIN, "refresh_solar_shading", handle_solar_refresh)
    hass.services.async_register(DOMAIN, "set_schedule_enabled", handle_set_enabled)

    # 6. Écoute des modifications d'options (toggle panneau)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("DomoLink-Planification v%s initialisé avec succès.", VERSION)
    return True


def _async_register_panel(hass: HomeAssistant) -> None:
    """Enregistre le panneau latéral Lovelace."""
    panel_url = f"{FRONTEND_URL_PATH}/{FRONTEND_FILE_NAME}?v={VERSION}"
    try:
        if hasattr(frontend, "add_extra_js_url"):
            frontend.add_extra_js_url(hass, panel_url)

        frontend.async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            frontend_url_path=PANEL_URL_PATH,
            config={
                "_panel_custom": {
                    "name": PANEL_NAME,
                    "module_url": panel_url,
                }
            },
            require_admin=False,
            update=True,
        )
        _LOGGER.info("DomoLink-Planification: Panneau latéral enregistré avec succès.")
    except Exception as err:
        _LOGGER.debug("Panneau latéral DomoLink-Planification déjà enregistré ou erreur: %s", err)


def _async_remove_panel(hass: HomeAssistant) -> None:
    """Retire le panneau latéral Lovelace."""
    try:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
        _LOGGER.info("DomoLink-Planification: Panneau latéral masqué conformément aux options.")
    except Exception as err:
        _LOGGER.debug("Erreur retrait panneau latéral : %s", err)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'intégration lors d'un changement d'options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge l'intégration proprement."""
    coordinator_data = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator_data:
        coordinator_data["coordinator"].async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


class DomolinkPlanificationApiView(HomeAssistantView):
    """Point d'accès REST API pour le panneau frontend DomoLink-Planification."""

    url = "/api/domolink_planification/{action}"
    name = "api:domolink_planification"
    requires_auth = True

    def __init__(self, coordinator: DomolinkPlanificationCoordinator) -> None:
        self.coordinator = coordinator

    async def get(self, request: web.Request, action: str) -> web.Response:
        """Récupère l'état complet, les plannings, l'historique et les paramètres."""
        if action == "data":
            data = {
                "schedules": self.coordinator.storage.get_schedules(),
                "history": self.coordinator.storage.get_history(),
                "settings": self.coordinator.storage.get_settings(),
                "next_runs": self.coordinator.data.get("next_runs", {}),
                "solar_states": self.coordinator.data.get("solar_states", {}),
            }
            return self.json(data)
        return self.json({"error": "Action inconnue"}, status=400)

    async def post(self, request: web.Request, action: str) -> web.Response:
        """Ajoute, modifie ou supprime une règle, ou déclenche une action."""
        try:
            body = await request.json()
        except Exception:
            body = {}

        if action == "save_schedule":
            sched_id = body.get("id") or f"rule_{int(self.coordinator.hass.loop.time() * 1000)}"
            await self.coordinator.storage.async_save_schedule(sched_id, body)
            self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())
            return self.json({"status": "ok", "id": sched_id})

        if action == "delete_schedule":
            sched_id = body.get("id")
            if sched_id:
                success = await self.coordinator.storage.async_delete_schedule(sched_id)
                self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())
                return self.json({"status": "ok" if success else "not_found"})
            return self.json({"error": "ID manquant"}, status=400)

        if action == "trigger_now":
            sched_id = body.get("id")
            if sched_id:
                res = await self.coordinator.async_trigger_now(sched_id)
                return self.json({"status": "ok" if res else "failed"})
            return self.json({"error": "ID manquant"}, status=400)

        if action == "save_settings":
            await self.coordinator.storage.async_update_settings(body)
            self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())
            return self.json({"status": "ok"})

        return self.json({"error": "Action inconnue"}, status=400)
