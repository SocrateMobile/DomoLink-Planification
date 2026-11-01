"""Stockage persistant sécurisé pour DomoLink-Planification."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    COUNTRY_FR,
    DEFAULT_GATE_CONFIG,
    HOLIDAY_MODE_ALWAYS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class PlanificationStorage:
    """Gestionnaire de persistance JSON dans le dossier .storage de Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {
            "schedules": {},
            "history": [],
            "settings": {
                "country": COUNTRY_FR,
                "holiday_mode": HOLIDAY_MODE_ALWAYS,
                "presence_entity": None,
                "alarm_entity": None,
                "vacation_mode": False,
                "solar_manual_override_minutes": 120,
            },
            "gate": dict(DEFAULT_GATE_CONFIG),
            "gates": {},
            "gate_history": [],
            "automations": {},
            "automation_traces": [],
        }

    async def async_load(self) -> dict[str, Any]:
        """Charge les données depuis le stockage persistant."""
        stored = await self._store.async_load()
        if stored:
            self.data = stored
            # Garantir les clés par défaut
            self.data.setdefault("schedules", {})
            self.data.setdefault("history", [])
            settings_data = self.data.setdefault("settings", {})
            settings_data.setdefault("country", COUNTRY_FR)
            settings_data.setdefault("holiday_mode", HOLIDAY_MODE_ALWAYS)
            settings_data.setdefault("presence_entity", None)
            settings_data.setdefault("alarm_entity", None)
            settings_data.setdefault("vacation_mode", False)
            settings_data.setdefault("solar_manual_override_minutes", 120)

            gate_data = self.data.setdefault("gate", {})
            for k, v in DEFAULT_GATE_CONFIG.items():
                gate_data.setdefault(k, v)
            
            # Migration & support multi-accès (portails, portes, garages)
            gates_data = self.data.setdefault("gates", {})
            if not gates_data and gate_data:
                primary_id = gate_data.get("id", "gate_1")
                gate_data["id"] = primary_id
                gate_data.setdefault("name", "Portail Principal")
                gates_data[primary_id] = gate_data

            for gid, gcfg in gates_data.items():
                for k, v in DEFAULT_GATE_CONFIG.items():
                    gcfg.setdefault(k, v)
                gcfg["id"] = gid

            self.data.setdefault("gate_history", [])
            self.data.setdefault("automations", {})
            self.data.setdefault("automation_traces", [])
            _LOGGER.info(
                "DomoLink-Planification: %d règle(s), %d accès, %d automatisation(s) chargée(s)",
                len(self.data["schedules"]),
                len(self.data["gates"]),
                len(self.data["automations"]),
            )

        else:
            _LOGGER.info("DomoLink-Planification: Nouveau stockage initialisé")
        return self.data

    async def async_save(self) -> None:
        """Enregistre les données actuelles de façon atomique."""
        await self._store.async_save(self.data)

    # -------------------------------------------------------------------------
    # Gestion des règles / plannings
    # -------------------------------------------------------------------------
    def get_schedules(self) -> dict[str, dict[str, Any]]:
        """Retourne toutes les règles enregistrées."""
        return self.data.get("schedules", {})

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        """Retourne une règle spécifique par son ID."""
        return self.data.get("schedules", {}).get(schedule_id)

    async def async_save_schedule(self, schedule_id: str, schedule_data: dict[str, Any]) -> None:
        """Crée ou met à jour une règle."""
        schedule_data["id"] = schedule_id
        self.data["schedules"][schedule_id] = schedule_data
        await self.async_save()

    async def async_delete_schedule(self, schedule_id: str) -> bool:
        """Supprime une règle par son ID."""
        if schedule_id in self.data["schedules"]:
            del self.data["schedules"][schedule_id]
            await self.async_save()
            return True
        return False

    # -------------------------------------------------------------------------
    # Historique d'audit (50 dernières actions)
    # -------------------------------------------------------------------------
    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retourne l'historique récent des exécutions."""
        return list(reversed(self.data.get("history", [])))[:limit]

    async def async_add_history(self, entry: dict[str, Any]) -> None:
        """Ajoute une entrée dans l'historique d'exécution (garde 100 max)."""
        history: list[dict[str, Any]] = self.data.setdefault("history", [])
        history.append(entry)
        if len(history) > 100:
            self.data["history"] = history[-100:]
        await self.async_save()

    # -------------------------------------------------------------------------
    # Paramètres globaux
    # -------------------------------------------------------------------------
    def get_settings(self) -> dict[str, Any]:
        """Retourne les paramètres généraux."""
        return self.data.get("settings", {})

    async def async_update_settings(self, new_settings: dict[str, Any]) -> None:
        """Met à jour les paramètres généraux."""
        self.data.setdefault("settings", {}).update(new_settings)
        await self.async_save()

    # -------------------------------------------------------------------------
    # Gestion Multi-Accès : Portails, Portes & Garages
    # -------------------------------------------------------------------------
    def get_gates(self) -> dict[str, dict[str, Any]]:
        """Retourne tous les accès configurés (portails, portes, garages)."""
        gates = self.data.get("gates", {})
        if not gates and "gate" in self.data:
            g = self.data["gate"]
            gid = g.get("id", "gate_1")
            return {gid: g}
        return gates

    def get_gate_config(self, gate_id: str | None = None) -> dict[str, Any]:
        """Retourne la configuration d'un accès spécifique ou du premier par défaut."""
        gates = self.get_gates()
        if gate_id and gate_id in gates:
            cfg = dict(DEFAULT_GATE_CONFIG)
            cfg.update(gates[gate_id])
            return cfg
        if gates:
            first_key = next(iter(gates))
            cfg = dict(DEFAULT_GATE_CONFIG)
            cfg.update(gates[first_key])
            return cfg
        cfg = dict(DEFAULT_GATE_CONFIG)
        cfg.update(self.data.get("gate", {}))
        return cfg

    async def async_save_gate(self, gate_id: str, new_config: dict[str, Any]) -> None:
        """Enregistre ou met à jour un portail / porte / accès."""
        new_config["id"] = gate_id
        gates = self.data.setdefault("gates", {})
        gates[gate_id] = new_config
        if gate_id == "gate_1" or len(gates) == 1:
            self.data["gate"] = new_config
        await self.async_save()

    async def async_update_gate_config(self, new_config: dict[str, Any]) -> None:
        """Met à jour la configuration du portail principal (rétrocompatibilité)."""
        gid = new_config.get("id") or "gate_1"
        await self.async_save_gate(gid, new_config)

    async def async_delete_gate(self, gate_id: str) -> bool:
        """Supprime un accès par son ID."""
        gates = self.data.setdefault("gates", {})
        if gate_id in gates:
            del gates[gate_id]
            if self.data.get("gate", {}).get("id") == gate_id:
                if gates:
                    self.data["gate"] = next(iter(gates.values()))
                else:
                    self.data["gate"] = dict(DEFAULT_GATE_CONFIG)
            await self.async_save()
            return True
        return False


    def get_gate_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retourne l'historique récent du portail."""
        return list(reversed(self.data.get("gate_history", [])))[:limit]

    async def async_add_gate_history(self, entry: dict[str, Any]) -> None:
        """Ajoute une entrée dans l'historique du portail (garde 100 max)."""
        history: list[dict[str, Any]] = self.data.setdefault("gate_history", [])
        history.append(entry)
        if len(history) > 100:
            self.data["gate_history"] = history[-100:]
        await self.async_save()

    # -------------------------------------------------------------------------
    # Gestion des Automatisations Modernes & Traces
    # -------------------------------------------------------------------------
    def get_automations(self) -> dict[str, dict[str, Any]]:
        """Retourne toutes les automatisations enregistrées."""
        return self.data.get("automations", {})

    def get_automation(self, automation_id: str) -> dict[str, Any] | None:
        """Retourne une automatisation spécifique par son ID."""
        return self.data.get("automations", {}).get(automation_id)

    async def async_save_automation(self, automation_id: str, auto_data: dict[str, Any]) -> None:
        """Crée ou met à jour une automatisation."""
        auto_data["id"] = automation_id
        self.data["automations"][automation_id] = auto_data
        await self.async_save()

    async def async_delete_automation(self, automation_id: str) -> bool:
        """Supprime une automatisation par son ID."""
        if automation_id in self.data.get("automations", {}):
            del self.data["automations"][automation_id]
            await self.async_save()
            return True
        return False

    def get_automation_traces(self, automation_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Retourne les traces d'exécution récentes."""
        traces: list[dict[str, Any]] = self.data.get("automation_traces", [])
        if automation_id:
            traces = [t for t in traces if t.get("automation_id") == automation_id]
        return list(reversed(traces))[:limit]

    async def async_add_automation_trace(self, trace_entry: dict[str, Any]) -> None:
        """Ajoute une trace d'exécution d'automatisation (garde 100 max)."""
        traces: list[dict[str, Any]] = self.data.setdefault("automation_traces", [])
        traces.append(trace_entry)
        if len(traces) > 100:
            self.data["automation_traces"] = traces[-100:]
        await self.async_save()


