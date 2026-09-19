"""Capteurs de diagnostic et d'état pour DomoLink-Planification."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NAME
from .coordinator import DomolinkPlanificationCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure les entités sensor depuis une ConfigEntry."""
    coordinator: DomolinkPlanificationCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    added_ids: set[str] = set()

    # Capteurs globaux
    global_entities = [
        PlanificationActiveCountSensor(coordinator, entry),
        PlanificationLastActionSensor(coordinator, entry),
    ]
    async_add_entities(global_entities)

    @callback
    def _update_entities() -> None:
        schedules = coordinator.storage.get_schedules()
        new_sensors = []
        for sched_id in schedules:
            if sched_id not in added_ids:
                added_ids.add(sched_id)
                new_sensors.append(PlanificationNextRunSensor(coordinator, entry, sched_id))
        if new_sensors:
            async_add_entities(new_sensors)

    _update_entities()
    entry.async_on_unload(coordinator.async_add_listener(_update_entities))


class PlanificationNextRunSensor(CoordinatorEntity[DomolinkPlanificationCoordinator], SensorEntity):
    """Capteur indiquant la prochaine exécution d'une règle."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-fast"

    def __init__(
        self,
        coordinator: DomolinkPlanificationCoordinator,
        entry: ConfigEntry,
        schedule_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.schedule_id = schedule_id
        self._attr_unique_id = f"domolink_planification_next_run_{schedule_id}"

    @property
    def _schedule(self) -> dict[str, Any]:
        return self.coordinator.storage.get_schedule(self.schedule_id) or {}

    @property
    def name(self) -> str:
        base_name = self._schedule.get("name", self.schedule_id)
        return f"{base_name} Prochaine Exécution"

    @property
    def native_value(self) -> str | datetime | None:
        """Retourne l'horodatage ou le statut de la prochaine exécution."""
        if not self._schedule.get("enabled", True):
            return "Désactivé"

        next_run = (self.coordinator.data or {}).get("next_runs", {}).get(self.schedule_id)
        if not next_run:
            return "Aucune"

        if next_run.startswith("Continu"):
            return next_run

        try:
            parsed = dt_util.parse_datetime(next_run)
            if parsed:
                return dt_util.as_local(parsed).strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass
        return str(next_run)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        next_run_raw = (self.coordinator.data or {}).get("next_runs", {}).get(self.schedule_id)
        sched = self._schedule
        return {
            "schedule_id": self.schedule_id,
            "next_run_raw": next_run_raw,
            "trigger_type": sched.get("trigger_type"),
            "target_type": sched.get("target_type"),
            "target_value": sched.get("target_value"),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "hub")},
            "name": NAME,
            "manufacturer": "DomoLink",
            "model": "Planification & Suivi Solaire",
        }


class PlanificationActiveCountSensor(CoordinatorEntity[DomolinkPlanificationCoordinator], SensorEntity):
    """Nombre total de planifications actives."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:counter"
    _attr_name = "Règles Actives"

    def __init__(self, coordinator: DomolinkPlanificationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = "domolink_planification_active_rules_count"

    @property
    def native_value(self) -> int:
        schedules = self.coordinator.storage.get_schedules()
        return sum(1 for s in schedules.values() if s.get("enabled", True))

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "hub")},
            "name": NAME,
            "manufacturer": "DomoLink",
            "model": "Planification & Suivi Solaire",
        }


class PlanificationLastActionSensor(CoordinatorEntity[DomolinkPlanificationCoordinator], SensorEntity):
    """Dernière action exécutée par le système."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:history"
    _attr_name = "Dernière Action Exécutée"

    def __init__(self, coordinator: DomolinkPlanificationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = "domolink_planification_last_executed_action"

    @property
    def native_value(self) -> str:
        history = self.coordinator.storage.get_history(limit=1)
        if not history:
            return "Aucune action récente"
        last = history[0]
        name = last.get("name", "Action")
        status = last.get("status", "OK")
        return f"{name} ({status})"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        history = self.coordinator.storage.get_history(limit=1)
        if not history:
            return {}
        return history[0]

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "hub")},
            "name": NAME,
            "manufacturer": "DomoLink",
            "model": "Planification & Suivi Solaire",
        }
