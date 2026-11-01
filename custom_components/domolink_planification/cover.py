"""Entités Cover natives pour les Portails, Portes et Garages DomoLink-Planification."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, GATE_TYPE_DOOR, GATE_TYPE_GARAGE
from .coordinator import DomolinkPlanificationCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure les entités cover dynamiques pour chaque accès DomoLink."""
    coordinator: DomolinkPlanificationCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    added_gate_ids: set[str] = set()

    @callback
    def _update_cover_entities() -> None:
        gates = coordinator.storage.get_gates()
        new_covers = []
        for gate_id in gates:
            if gate_id not in added_gate_ids:
                added_gate_ids.add(gate_id)
                new_covers.append(DomoLinkGateCover(coordinator, entry, gate_id))
        if new_covers:
            async_add_entities(new_covers)

    _update_cover_entities()
    entry.async_on_unload(coordinator.async_add_listener(_update_cover_entities))


class DomoLinkGateCover(CoordinatorEntity[DomolinkPlanificationCoordinator], CoverEntity):
    """Entité Cover représentant un Portail, une Porte ou un Garage DomoLink."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(
        self,
        coordinator: DomolinkPlanificationCoordinator,
        entry: ConfigEntry,
        gate_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.gate_id = gate_id
        self._attr_unique_id = f"{entry.entry_id}_cover_{gate_id}"

    @property
    def _gate_info(self) -> dict[str, Any]:
        gates_status = (self.coordinator.data or {}).get("gates", {})
        if self.gate_id in gates_status:
            return gates_status[self.gate_id]
        return self.coordinator.get_gate_status(self.gate_id)

    @property
    def name(self) -> str:
        return self._gate_info.get("name", f"Accès {self.gate_id}")

    @property
    def device_class(self) -> CoverDeviceClass:
        g_type = self._gate_info.get("gate_type")
        if g_type == GATE_TYPE_GARAGE:
            return CoverDeviceClass.GARAGE
        if g_type == GATE_TYPE_DOOR:
            return CoverDeviceClass.DOOR
        return CoverDeviceClass.GATE

    @property
    def is_closed(self) -> bool:
        return self._gate_info.get("state", "closed") == "closed"

    @property
    def is_opening(self) -> bool:
        return self._gate_info.get("state") == "opening"

    @property
    def is_closing(self) -> bool:
        return self._gate_info.get("state") == "closing"

    @property
    def current_cover_position(self) -> int:
        st = self._gate_info.get("state", "closed")
        prog = float(self._gate_info.get("movement_progress", 0.0))
        if st == "closed":
            return 0
        if st == "opening":
            return max(1, min(99, int(round(prog))))
        if st == "closing":
            return max(1, min(99, 100 - int(round(prog))))
        return 100

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Ouvre l'accès."""
        await self.coordinator.async_gate_trigger_action(mode="open", gate_id=self.gate_id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Ferme l'accès."""
        await self.coordinator.async_gate_trigger_action(mode="close", gate_id=self.gate_id)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stoppe ou bascule l'accès."""
        await self.coordinator.async_gate_trigger_action(mode="toggle", gate_id=self.gate_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._gate_info
        return {
            "gate_id": self.gate_id,
            "gate_type": info.get("gate_type"),
            "domolink_state": info.get("state"),
            "countdown_seconds": info.get("countdown_seconds", 0),
            "hold_open": info.get("hold_open", False),
            "hold_open_until": info.get("hold_open_until"),
            "retries_done": info.get("retries_done", 0),
            "last_action": info.get("last_action"),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "gate")},
            "name": "DomoLink Portail & Accès",
            "manufacturer": "DomoLink",
            "model": "Contrôleur Multi-Accès Universel",
        }
