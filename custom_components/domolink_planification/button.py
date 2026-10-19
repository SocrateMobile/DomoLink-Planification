"""Entités Bouton pour DomoLink-Planification (Test manuel immédiat)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import DomolinkPlanificationCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure les entités button depuis une ConfigEntry."""
    coordinator: DomolinkPlanificationCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    added_ids: set[str] = set()

    # Bouton global de réévaluation des volets et boutons portail
    async_add_entities([
        PlanificationSolarRefreshButton(coordinator, entry),
        GateTriggerButton(coordinator, entry),
        GateCloseButton(coordinator, entry),
        GatePedestrianButton(coordinator, entry),
    ])

    @callback
    def _update_entities() -> None:
        schedules = coordinator.storage.get_schedules()
        new_buttons = []
        for sched_id in schedules:
            if sched_id not in added_ids:
                added_ids.add(sched_id)
                new_buttons.append(PlanificationTriggerNowButton(coordinator, entry, sched_id))
        if new_buttons:
            async_add_entities(new_buttons)

    _update_entities()
    entry.async_on_unload(coordinator.async_add_listener(_update_entities))


class PlanificationTriggerNowButton(CoordinatorEntity[DomolinkPlanificationCoordinator], ButtonEntity):
    """Bouton pour tester et exécuter immédiatement une planification."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:play-circle-outline"

    def __init__(
        self,
        coordinator: DomolinkPlanificationCoordinator,
        entry: ConfigEntry,
        schedule_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.schedule_id = schedule_id
        self._attr_unique_id = f"domolink_planification_trigger_btn_{schedule_id}"

    @property
    def name(self) -> str:
        sched = self.coordinator.storage.get_schedule(self.schedule_id) or {}
        base_name = sched.get("name", self.schedule_id)
        return f"{base_name} Tester Immédiatement"

    async def async_press(self) -> None:
        """Déclenche la règle immédiatement."""
        await self.coordinator.async_trigger_now(self.schedule_id)

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "hub")},
            "name": NAME,
            "manufacturer": "DomoLink",
            "model": "Planification & Suivi Solaire",
        }


class PlanificationSolarRefreshButton(CoordinatorEntity[DomolinkPlanificationCoordinator], ButtonEntity):
    """Bouton pour forcer la réévaluation immédiate de tous les volets solaires."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:weather-sunny"
    _attr_name = "Réévaluer Volets Solaires"

    def __init__(self, coordinator: DomolinkPlanificationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = "domolink_planification_solar_refresh_button"

    async def async_press(self) -> None:
        """Force la réévaluation des volets solaires."""
        now = self.coordinator.hass.util.dt.now() if hasattr(self.coordinator.hass.util, "dt") else None
        from homeassistant.util import dt as dt_util
        await self.coordinator._evaluate_solar_shading_rules(dt_util.now())
        self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "hub")},
            "name": NAME,
            "manufacturer": "DomoLink",
            "model": "Planification & Suivi Solaire",
        }


class GateTriggerButton(CoordinatorEntity[DomolinkPlanificationCoordinator], ButtonEntity):
    """Bouton pour actionner le portail (impulsion ouverture / arrêt / fermeture)."""

    _attr_has_entity_name = True
    _attr_name = "Portail Actionner"
    _attr_icon = "mdi:gate"

    def __init__(self, coordinator: DomolinkPlanificationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_gate_trigger_button"

    async def async_press(self) -> None:
        """Déclenche la commande du portail."""
        await self.coordinator.async_gate_trigger_action(mode="toggle")

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "gate")},
            "name": "DomoLink Portail",
            "manufacturer": "DomoLink",
            "model": "Contrôleur d'Accès Universel",
        }


class GateCloseButton(CoordinatorEntity[DomolinkPlanificationCoordinator], ButtonEntity):
    """Bouton pour forcer la fermeture immédiate du portail."""

    _attr_has_entity_name = True
    _attr_name = "Portail Fermer"
    _attr_icon = "mdi:gate-arrow-right"

    def __init__(self, coordinator: DomolinkPlanificationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_gate_close_button"

    async def async_press(self) -> None:
        """Déclenche la fermeture du portail."""
        await self.coordinator.async_gate_trigger_action(mode="close")

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "gate")},
            "name": "DomoLink Portail",
            "manufacturer": "DomoLink",
            "model": "Contrôleur d'Accès Universel",
        }


class GatePedestrianButton(CoordinatorEntity[DomolinkPlanificationCoordinator], ButtonEntity):
    """Bouton pour actionner l'accès piéton du portail."""

    _attr_has_entity_name = True
    _attr_name = "Portail Accès Piéton"
    _attr_icon = "mdi:walk"

    def __init__(self, coordinator: DomolinkPlanificationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_gate_pedestrian_button"

    async def async_press(self) -> None:
        """Déclenche la commande d'accès piéton."""
        await self.coordinator.async_gate_trigger_action(mode="pedestrian")

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "gate")},
            "name": "DomoLink Portail",
            "manufacturer": "DomoLink",
            "model": "Contrôleur d'Accès Universel",
        }


