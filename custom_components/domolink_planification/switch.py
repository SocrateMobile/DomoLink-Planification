"""Entités Switch pour activer/désactiver les règles DomoLink-Planification."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Configure les entités switch depuis une ConfigEntry."""
    coordinator: DomolinkPlanificationCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    added_ids: set[str] = set()

    # Interrupteurs du Portail DomoLink
    async_add_entities([
        GateAutoCloseSwitch(coordinator, entry),
        GateHoldOpenSwitch(coordinator, entry),
    ])

    @callback
    def _update_entities() -> None:
        schedules = coordinator.storage.get_schedules()
        new_entities = []
        for sched_id, sched_data in schedules.items():
            if sched_id not in added_ids:
                added_ids.add(sched_id)
                new_entities.append(PlanificationSwitch(coordinator, entry, sched_id))
        if new_entities:
            async_add_entities(new_entities)

    _update_entities()
    entry.async_on_unload(coordinator.async_add_listener(_update_entities))


class PlanificationSwitch(CoordinatorEntity[DomolinkPlanificationCoordinator], SwitchEntity):
    """Interrupteur permettant d'activer ou de suspendre une planification."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-check"

    def __init__(
        self,
        coordinator: DomolinkPlanificationCoordinator,
        entry: ConfigEntry,
        schedule_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.schedule_id = schedule_id
        self._attr_unique_id = f"domolink_planification_switch_{schedule_id}"

    @property
    def _schedule(self) -> dict[str, Any]:
        """Retourne la configuration actuelle de la règle."""
        return self.coordinator.storage.get_schedule(self.schedule_id) or {}

    @property
    def name(self) -> str:
        """Nom de l'entité."""
        return self._schedule.get("name", f"Planning {self.schedule_id}")

    @property
    def is_on(self) -> bool:
        """État d'activation du planning."""
        return bool(self._schedule.get("enabled", True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Active la planification."""
        sched = self._schedule
        sched["enabled"] = True
        await self.coordinator.storage.async_save_schedule(self.schedule_id, sched)
        self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Suspend la planification."""
        sched = self._schedule
        sched["enabled"] = False
        await self.coordinator.storage.async_save_schedule(self.schedule_id, sched)
        self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributs détaillés de la règle."""
        sched = self._schedule
        next_run = (self.coordinator.data or {}).get("next_runs", {}).get(self.schedule_id)
        return {
            "schedule_id": self.schedule_id,
            "trigger_type": sched.get("trigger_type"),
            "target_type": sched.get("target_type"),
            "target_value": sched.get("target_value"),
            "next_run": next_run,
            "holiday_mode": sched.get("holiday_mode"),
            "presence_condition": sched.get("presence_condition"),
            "alarm_condition": sched.get("alarm_condition"),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """Associe l'entité au hub DomoLink-Planification."""
        return {
            "identifiers": {(DOMAIN, "hub")},
            "name": NAME,
            "manufacturer": "DomoLink",
            "model": "Planification & Suivi Solaire",
        }


class GateAutoCloseSwitch(CoordinatorEntity[DomolinkPlanificationCoordinator], SwitchEntity):
    """Interrupteur activant ou suspendant la fermeture automatique du portail."""

    _attr_has_entity_name = True
    _attr_name = "Portail Fermeture Automatique"
    _attr_icon = "mdi:gate"

    def __init__(
        self,
        coordinator: DomolinkPlanificationCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_gate_auto_close"

    @property
    def is_on(self) -> bool:
        """Retourne si la fermeture automatique est activée."""
        cfg = self.coordinator.storage.get_gate_config()
        return bool(cfg.get("enabled", True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Active la fermeture automatique."""
        cfg = self.coordinator.storage.get_gate_config()
        cfg["enabled"] = True
        await self.coordinator.storage.async_update_gate_config(cfg)
        self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Désactive la fermeture automatique."""
        cfg = self.coordinator.storage.get_gate_config()
        cfg["enabled"] = False
        await self.coordinator.storage.async_update_gate_config(cfg)
        self.coordinator.async_set_updated_data(await self.coordinator._async_update_data())

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "gate")},
            "name": "DomoLink Portail",
            "manufacturer": "DomoLink",
            "model": "Contrôleur d'Accès Universel",
        }


class GateHoldOpenSwitch(CoordinatorEntity[DomolinkPlanificationCoordinator], SwitchEntity):
    """Interrupteur de maintien ouvert permanent (mode travaux / réception)."""

    _attr_has_entity_name = True
    _attr_name = "Portail Maintien Ouvert"
    _attr_icon = "mdi:lock-open-variant-outline"

    def __init__(
        self,
        coordinator: DomolinkPlanificationCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_gate_hold_open"

    @property
    def is_on(self) -> bool:
        """Retourne si le maintien ouvert est actif."""
        cfg = self.coordinator.storage.get_gate_config()
        return bool(cfg.get("hold_open", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Active le maintien ouvert."""
        await self.coordinator.async_gate_set_hold_open(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Désactive le maintien ouvert."""
        await self.coordinator.async_gate_set_hold_open(False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cfg = self.coordinator.storage.get_gate_config()
        return {
            "hold_open_until": cfg.get("hold_open_until"),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "gate")},
            "name": "DomoLink Portail",
            "manufacturer": "DomoLink",
            "model": "Contrôleur d'Accès Universel",
        }

