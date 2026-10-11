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
            },
            "gate": dict(DEFAULT_GATE_CONFIG),
            "gate_history": [],
        }

    async def async_load(self) -> dict[str, Any]:
        """Charge les données depuis le stockage persistant."""
        stored = await self._store.async_load()
        if stored:
            self.data = stored
            # Garantir les clés par défaut
            self.data.setdefault("schedules", {})
            self.data.setdefault("history", [])
            self.data.setdefault("settings", {
                "country": COUNTRY_FR,
                "holiday_mode": HOLIDAY_MODE_ALWAYS,
                "presence_entity": None,
                "alarm_entity": None,
            })
            gate_data = self.data.setdefault("gate", {})
            for k, v in DEFAULT_GATE_CONFIG.items():
                gate_data.setdefault(k, v)
            self.data.setdefault("gate_history", [])
            _LOGGER.info("DomoLink-Planification: %d règle(s) chargée(s) depuis le stockage", len(self.data["schedules"]))
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
    # Gestion du Portail & Accès
    # -------------------------------------------------------------------------
    def get_gate_config(self) -> dict[str, Any]:
        """Retourne la configuration du portail."""
        cfg = dict(DEFAULT_GATE_CONFIG)
        cfg.update(self.data.get("gate", {}))
        return cfg

    async def async_update_gate_config(self, new_config: dict[str, Any]) -> None:
        """Met à jour la configuration du portail."""
        gate_data = self.data.setdefault("gate", dict(DEFAULT_GATE_CONFIG))
        gate_data.update(new_config)
        await self.async_save()

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

