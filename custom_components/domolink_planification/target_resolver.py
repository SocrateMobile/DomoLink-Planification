"""Résolveur de cibles universel pour DomoLink-Planification (Entités, Étiquettes, Pièces, Scripts...)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    TARGET_TYPE_AREA,
    TARGET_TYPE_AUTOMATION,
    TARGET_TYPE_ENTITY,
    TARGET_TYPE_LABEL,
    TARGET_TYPE_NOTIFICATION,
    TARGET_TYPE_SCENE,
    TARGET_TYPE_SCRIPT,
    TARGET_TYPE_SEQUENCE,
)

_LOGGER = logging.getLogger(__name__)


class TargetResolver:
    """Résout dynamiquement les entités cibles selon le type (étiquettes, pièces, etc.) et exécute les actions."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    def resolve_entities(self, target_type: str, target_value: Any) -> list[str]:
        """Résout une cible en une liste concrète d'entity_ids."""
        if not target_value:
            return []

        # 1. Cible Entité(s) directe(s)
        if target_type == TARGET_TYPE_ENTITY:
            if isinstance(target_value, list):
                return [str(e) for e in target_value if e]
            return [str(target_value)]

        # 2. Cible Étiquette (Label natif HA 2024+)
        if target_type == TARGET_TYPE_LABEL:
            return self._resolve_by_label(str(target_value))

        # 3. Cible Zone / Pièce (Area)
        if target_type == TARGET_TYPE_AREA:
            return self._resolve_by_area(str(target_value))

        # 4. Script direct
        if target_type == TARGET_TYPE_SCRIPT:
            script_id = str(target_value)
            if not script_id.startswith("script."):
                script_id = f"script.{script_id}"
            return [script_id]

        # 5. Automatisation
        if target_type == TARGET_TYPE_AUTOMATION:
            auto_id = str(target_value)
            if not auto_id.startswith("automation."):
                auto_id = f"automation.{auto_id}"
            return [auto_id]

        # 6. Scène
        if target_type == TARGET_TYPE_SCENE:
            scene_id = str(target_value)
            if not scene_id.startswith("scene."):
                scene_id = f"scene.{scene_id}"
            return [scene_id]

        return []

    def _resolve_by_label(self, label_id_or_name: str) -> list[str]:
        """Trouve toutes les entités associées à une étiquette donnée."""
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)

        # Chercher le label dans le label_registry si disponible
        target_label_id = label_id_or_name
        try:
            from homeassistant.helpers import label_registry as lr
            label_reg = lr.async_get(self.hass)
            # Vérifier si c'est un nom d'étiquette plutôt qu'un ID
            for lbl in label_reg.labels.values():
                if lbl.name.lower() == label_id_or_name.lower() or lbl.label_id.lower() == label_id_or_name.lower():
                    target_label_id = lbl.label_id
                    break
        except Exception:
            pass

        resolved: set[str] = set()

        # A. Entités directement étiquetées
        for entity in ent_reg.entities.values():
            labels = entity.labels or []
            if target_label_id in labels or label_id_or_name in labels:
                resolved.add(entity.entity_id)

        # B. Appareils étiquetés (inclure toutes les entités de l'appareil)
        devices_with_label = set()
        for device in dev_reg.devices.values():
            dev_labels = device.labels or []
            if target_label_id in dev_labels or label_id_or_name in dev_labels:
                devices_with_label.add(device.id)

        if devices_with_label:
            for entity in ent_reg.entities.values():
                if entity.device_id in devices_with_label:
                    resolved.add(entity.entity_id)

        _LOGGER.debug(
            "DomoLink-Planification: Étiquette '%s' résolue vers %d entité(s) : %s",
            label_id_or_name,
            len(resolved),
            list(resolved),
        )
        return sorted(list(resolved))

    def _resolve_by_area(self, area_id_or_name: str) -> list[str]:
        """Trouve toutes les entités rattachées à une pièce / zone."""
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        area_reg = ar.async_get(self.hass)

        target_area_id = area_id_or_name
        for area in area_reg.areas.values():
            if area.name.lower() == area_id_or_name.lower() or area.id.lower() == area_id_or_name.lower():
                target_area_id = area.id
                break

        resolved: set[str] = set()
        devices_in_area = {d.id for d in dev_reg.devices.values() if d.area_id == target_area_id}

        for entity in ent_reg.entities.values():
            if entity.area_id == target_area_id or entity.device_id in devices_in_area:
                resolved.add(entity.entity_id)

        return sorted(list(resolved))

    async def execute_action(
        self,
        target_type: str,
        target_value: Any,
        action_data: dict[str, Any],
    ) -> bool:
        """Exécute l'action programmée sur la ou les cibles résolues."""
        try:
            # Séquence multi-étapes
            if target_type == TARGET_TYPE_SEQUENCE:
                steps = action_data.get("steps", [])
                for i, step in enumerate(steps):
                    st_type = step.get("target_type", TARGET_TYPE_ENTITY)
                    st_val = step.get("target_value")
                    st_data = step.get("action_data", {})
                    delay = float(step.get("delay_seconds", 0.0))

                    _LOGGER.info("DomoLink-Planification: Exécution étape %d/%d de la séquence", i + 1, len(steps))
                    await self.execute_action(st_type, st_val, st_data)
                    if delay > 0:
                        await asyncio.sleep(delay)
                return True

            # Notification
            if target_type == TARGET_TYPE_NOTIFICATION:
                msg = action_data.get("message", "Alerte DomoLink-Planification")
                title = action_data.get("title", "DomoLink-Planification")
                notify_service = action_data.get("notify_service", "notify")
                domain = "notify"
                service = notify_service.replace("notify.", "") if "." in notify_service else notify_service

                await self.hass.services.async_call(
                    domain,
                    service,
                    {"message": msg, "title": title},
                    blocking=True,
                )
                return True

            # Scripts
            if target_type == TARGET_TYPE_SCRIPT:
                entities = self.resolve_entities(target_type, target_value)
                for ent in entities:
                    script_name = ent.replace("script.", "")
                    await self.hass.services.async_call("script", script_name, action_data.get("data", {}), blocking=True)
                return True

            # Automatisations
            if target_type == TARGET_TYPE_AUTOMATION:
                entities = self.resolve_entities(target_type, target_value)
                for ent in entities:
                    await self.hass.services.async_call("automation", "trigger", {"entity_id": ent}, blocking=True)
                return True

            # Scènes
            if target_type == TARGET_TYPE_SCENE:
                entities = self.resolve_entities(target_type, target_value)
                for ent in entities:
                    await self.hass.services.async_call("scene", "turn_on", {"entity_id": ent}, blocking=True)
                return True

            # Entités ou Étiquettes ou Pièces (appels de service standard)
            entities = self.resolve_entities(target_type, target_value)
            if not entities:
                _LOGGER.warning("DomoLink-Planification: Aucune entité trouvée pour la cible '%s' (%s)", target_value, target_type)
                return False

            domain = action_data.get("domain")
            service = action_data.get("service")
            service_data = dict(action_data.get("data", {}))

            # Si le service n'est pas spécifié, déduire du domaine de la première entité
            if not domain or not service:
                first_ent = entities[0]
                ent_domain = first_ent.split(".")[0]
                domain = domain or ent_domain
                service = service or "turn_on"

            # Grouper par domaine si plusieurs domaines différents
            entities_by_domain: dict[str, list[str]] = {}
            for eid in entities:
                d = eid.split(".")[0]
                entities_by_domain.setdefault(d, []).append(eid)

            for d, eids in entities_by_domain.items():
                call_domain = domain if len(entities_by_domain) == 1 else d
                call_service = service
                call_data = dict(service_data)
                call_data["entity_id"] = eids

                _LOGGER.info(
                    "DomoLink-Planification: Appel %s.%s sur %d entité(s) : %s",
                    call_domain,
                    call_service,
                    len(eids),
                    eids,
                )
                await self.hass.services.async_call(call_domain, call_service, call_data, blocking=True)

            return True

        except Exception as err:
            _LOGGER.error("DomoLink-Planification: Erreur lors de l'exécution de l'action : %s", err, exc_info=True)
            return False
