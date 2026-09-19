"""Coordinateur central et moteur d'exécution pour DomoLink-Planification."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
import random
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    HOLIDAY_MODE_ALWAYS,
    HOLIDAY_MODE_EXCLUDE,
    HOLIDAY_MODE_ONLY,
    HOLIDAY_MODE_WEEKEND,
    TRIGGER_TYPE_INTERVAL,
    TRIGGER_TYPE_ONCE,
    TRIGGER_TYPE_SOLAR,
    TRIGGER_TYPE_SOLAR_SHADING,
    TRIGGER_TYPE_TIME,
)
from .holidays import HolidayEngine
from .solar_shading import SolarShadingEvaluator
from .storage import PlanificationStorage
from .target_resolver import TargetResolver

_LOGGER = logging.getLogger(__name__)


class DomolinkPlanificationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinateur gérant la planification, le suivi solaire et l'exécution des actions."""

    def __init__(self, hass: HomeAssistant, storage: PlanificationStorage) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.storage = storage
        self.resolver = TargetResolver(hass)
        self.solar_shading = SolarShadingEvaluator(hass)
        self._last_evaluated_minute: str | None = None
        self._solar_shading_states: dict[str, dict[str, Any]] = {}
        self._remove_timer: Any = None

    async def async_init(self) -> None:
        """Initialise le stockage et lance la boucle de synchronisation temporelle."""
        await self.storage.async_load()
        self.data = {
            "schedules": self.storage.get_schedules(),
            "history": self.storage.get_history(),
            "settings": self.storage.get_settings(),
            "next_runs": self.compute_all_next_runs(),
        }

        # Démarrer la boucle périodique de vérification (chaque 30s)
        self._remove_timer = async_track_time_interval(
            self.hass,
            self._async_tick,
            timedelta(seconds=30),
        )
        _LOGGER.info("DomoLink-Planification: Moteur de planification et suivi solaire démarré.")

    def async_stop(self) -> None:
        """Arrête les boucles en arrière-plan."""
        if self._remove_timer:
            self._remove_timer()
            self._remove_timer = None

    async def _async_tick(self, now: datetime) -> None:
        """Vérification périodique des déclencheurs et du suivi solaire."""
        now_local = dt_util.as_local(now)
        current_minute = now_local.strftime("%Y-%m-%d %H:%M")

        # 1. Évaluation des volets solaires (chaque minute)
        await self._evaluate_solar_shading_rules(now_local)

        # 2. Évaluation des règles temporelles (une seule fois par minute)
        if current_minute != self._last_evaluated_minute:
            self._last_evaluated_minute = current_minute
            await self._evaluate_time_rules(now_local)

        # 3. Rafraîchir les données et notifier les entités
        self.data = {
            "schedules": self.storage.get_schedules(),
            "history": self.storage.get_history(),
            "settings": self.storage.get_settings(),
            "next_runs": self.compute_all_next_runs(),
            "solar_states": self._solar_shading_states,
        }
        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Méthode appelée par DataUpdateCoordinator."""
        return {
            "schedules": self.storage.get_schedules(),
            "history": self.storage.get_history(),
            "settings": self.storage.get_settings(),
            "next_runs": self.compute_all_next_runs(),
            "solar_states": self._solar_shading_states,
        }

    # -------------------------------------------------------------------------
    # Évaluation des règles de suivi solaire (Volets)
    # -------------------------------------------------------------------------
    async def _evaluate_solar_shading_rules(self, now: datetime) -> None:
        """Parcourt les règles de type suivi solaire et positionne les volets."""
        schedules = self.storage.get_schedules()
        for sched_id, sched in schedules.items():
            if not sched.get("enabled", True):
                continue
            if sched.get("trigger_type") != TRIGGER_TYPE_SOLAR_SHADING:
                continue

            last_state = self._solar_shading_states.get(sched_id)
            eval_result = self.solar_shading.evaluate_rule(sched, last_state)
            self._solar_shading_states[sched_id] = eval_result

            # Si une action est requise (changement de position nécessaire)
            if eval_result.get("should_act"):
                cover_id = eval_result.get("cover_entity_id")
                target_pos = eval_result.get("target_position")
                reason = eval_result.get("reason", "")

                if cover_id and target_pos is not None:
                    _LOGGER.info("DomoLink-Planification [Volet Solaire] %s : %s", cover_id, reason)
                    try:
                        await self.hass.services.async_call(
                            "cover",
                            "set_cover_position",
                            {"entity_id": cover_id, "position": target_pos},
                            blocking=True,
                        )
                        await self.storage.async_add_history({
                            "timestamp": now.isoformat(),
                            "schedule_id": sched_id,
                            "name": sched.get("name", "Volet Solaire"),
                            "status": "SUCCESS",
                            "details": reason,
                        })
                    except Exception as err:
                        _LOGGER.error("Erreur commande volet %s : %s", cover_id, err)

    # -------------------------------------------------------------------------
    # Évaluation des règles temporelles (Heure, Solaire, Ponctuel, Intervalle)
    # -------------------------------------------------------------------------
    async def _evaluate_time_rules(self, now: datetime) -> None:
        """Vérifie si des règles temporelles doivent se déclencher à la minute courante."""
        schedules = self.storage.get_schedules()
        settings = self.storage.get_settings()
        country = settings.get("country", "FR")

        for sched_id, sched in list(schedules.items()):
            if not sched.get("enabled", True):
                continue

            trigger_type = sched.get("trigger_type", TRIGGER_TYPE_TIME)
            if trigger_type == TRIGGER_TYPE_SOLAR_SHADING:
                continue

            if not self._check_trigger_match(sched, now):
                continue

            # Vérifier les conditions (Présence, Alarme, Jours fériés)
            condition_met, cond_reason = self._check_conditions(sched, now, country)
            if not condition_met:
                _LOGGER.info("DomoLink-Planification [%s] Ignoré : %s", sched.get("name"), cond_reason)
                await self.storage.async_add_history({
                    "timestamp": now.isoformat(),
                    "schedule_id": sched_id,
                    "name": sched.get("name", sched_id),
                    "status": "SKIPPED",
                    "details": cond_reason,
                })
                continue

            # Déclenchement de l'action
            _LOGGER.info("DomoLink-Planification [%s] Déclenchement de l'action...", sched.get("name"))
            success = await self.resolver.execute_action(
                target_type=sched.get("target_type"),
                target_value=sched.get("target_value"),
                action_data=sched.get("action_data", {}),
            )

            # Enregistrer dans l'historique
            await self.storage.async_add_history({
                "timestamp": now.isoformat(),
                "schedule_id": sched_id,
                "name": sched.get("name", sched_id),
                "status": "SUCCESS" if success else "FAILED",
                "details": f"Cible: {sched.get('target_type')} ({sched.get('target_value')})",
            })

            # Si c'était un déclencheur ponctuel (One-shot), désactiver la règle
            if trigger_type == TRIGGER_TYPE_ONCE:
                sched["enabled"] = False
                await self.storage.async_save_schedule(sched_id, sched)

    def _check_trigger_match(self, sched: dict[str, Any], now: datetime) -> bool:
        """Vérifie si l'heure et la date courantes correspondent au déclencheur."""
        trigger_type = sched.get("trigger_type", TRIGGER_TYPE_TIME)

        # 1. Ponctuel (Date & Heure précises ISO)
        if trigger_type == TRIGGER_TYPE_ONCE:
            target_iso = sched.get("target_datetime")
            if not target_iso:
                return False
            try:
                target_dt = dt_util.parse_datetime(target_iso)
                if not target_dt:
                    return False
                target_local = dt_util.as_local(target_dt)
                return (
                    now.year == target_local.year
                    and now.month == target_local.month
                    and now.day == target_local.day
                    and now.hour == target_local.hour
                    and now.minute == target_local.minute
                )
            except Exception:
                return False

        # 2. Heure quotidienne / hebdomadaire
        if trigger_type == TRIGGER_TYPE_TIME:
            target_time_str = sched.get("time", "00:00")
            try:
                target_h, target_m = [int(p) for p in target_time_str.split(":")[:2]]
            except Exception:
                return False

            if now.hour != target_h or now.minute != target_m:
                return False

            # Vérifier les jours de la semaine (0=Lundi, 6=Dimanche)
            weekdays = sched.get("weekdays")
            if weekdays is not None and len(weekdays) > 0:
                if now.weekday() not in weekdays:
                    return False

            # Vérifier les mois sélectionnés si spécifiés
            months = sched.get("months")
            if months is not None and len(months) > 0:
                if now.month not in months:
                    return False

            # Vérifier les jours du mois si spécifiés
            days_of_month = sched.get("days_of_month")
            if days_of_month is not None and len(days_of_month) > 0:
                if now.day not in days_of_month:
                    return False

            return True

        # 3. Événement Solaire (Lever / Coucher de soleil)
        if trigger_type == TRIGGER_TYPE_SOLAR:
            solar_event = sched.get("solar_event", "sunset")
            offset_minutes = int(sched.get("solar_offset_minutes", 0))

            sun_state = self.hass.states.get("sun.sun")
            if not sun_state:
                return False

            attr_key = "next_rising" if solar_event == "sunrise" else "next_setting"
            event_iso = sun_state.attributes.get(attr_key)
            if not event_iso:
                return False

            try:
                event_dt = dt_util.parse_datetime(event_iso)
                if not event_dt:
                    return False
                target_time = dt_util.as_local(event_dt) + timedelta(minutes=offset_minutes)
                return now.hour == target_time.hour and now.minute == target_time.minute
            except Exception:
                return False

        return False

    def _check_conditions(self, sched: dict[str, Any], now: datetime, country: str) -> tuple[bool, str]:
        """Vérifie si toutes les conditions de garde-fous sont réunies."""
        today = now.date()

        # 1. Jours Fériés
        holiday_mode = sched.get("holiday_mode", HOLIDAY_MODE_ALWAYS)
        is_holiday = HolidayEngine.is_holiday(today, country)

        if holiday_mode == HOLIDAY_MODE_EXCLUDE and is_holiday:
            name = HolidayEngine.get_holiday_name(today, country)
            return False, f"Jour férié ({name}) exclu par la règle"

        if holiday_mode == HOLIDAY_MODE_ONLY and not is_holiday:
            return False, "La règle ne s'exécute que les jours fériés"

        if holiday_mode == HOLIDAY_MODE_WEEKEND and is_holiday:
            weekdays = sched.get("weekdays")
            if weekdays is not None and 6 not in weekdays:  # Si le dimanche n'est pas autorisé
                return False, "Jour férié traité comme dimanche (non actif pour ce jour)"

        # 2. Présence
        presence_mode = sched.get("presence_condition")  # 'home', 'away', or None
        presence_entity = sched.get("presence_entity") or self.storage.get_settings().get("presence_entity")
        if presence_mode and presence_entity:
            p_state = self.hass.states.get(presence_entity)
            if p_state:
                is_home = p_state.state in ("home", "on", "true")
                if presence_mode == "home" and not is_home:
                    return False, f"Présence requise : personne à la maison ({presence_entity}={p_state.state})"
                if presence_mode == "away" and is_home:
                    return False, f"Absence requise : présence détectée ({presence_entity}={p_state.state})"

        # 3. Alarme (DomoLink-Alarm ou alarme HA standard)
        alarm_mode = sched.get("alarm_condition")  # 'disarmed', 'armed', or None
        alarm_entity = sched.get("alarm_entity") or self.storage.get_settings().get("alarm_entity")
        if alarm_mode and alarm_entity:
            a_state = self.hass.states.get(alarm_entity)
            if a_state:
                is_disarmed = a_state.state in ("disarmed", "off")
                if alarm_mode == "disarmed" and not is_disarmed:
                    return False, f"Alarme armée ({alarm_entity}={a_state.state}) ➔ action annulée"
                if alarm_mode == "armed" and is_disarmed:
                    return False, f"Alarme désarmée ({alarm_entity}={a_state.state}) ➔ action annulée"

        return True, "Conditions validées"

    # -------------------------------------------------------------------------
    # Calcul des prochaines exécutions (pour les sensors & l'interface)
    # -------------------------------------------------------------------------
    def compute_all_next_runs(self) -> dict[str, str | None]:
        """Calcule la prochaine date/heure d'exécution pour chaque règle."""
        schedules = self.storage.get_schedules()
        now = dt_util.now()
        results: dict[str, str | None] = {}

        for sched_id, sched in schedules.items():
            if not sched.get("enabled", True):
                results[sched_id] = None
                continue

            t_type = sched.get("trigger_type", TRIGGER_TYPE_TIME)
            if t_type == TRIGGER_TYPE_SOLAR_SHADING:
                results[sched_id] = "Continu (Suivi solaire)"
                continue

            if t_type == TRIGGER_TYPE_ONCE:
                results[sched_id] = sched.get("target_datetime")
                continue

            if t_type == TRIGGER_TYPE_TIME:
                time_str = sched.get("time", "00:00")
                try:
                    h, m = [int(p) for p in time_str.split(":")[:2]]
                    # Chercher dans les 7 prochains jours
                    for day_offset in range(14):
                        candidate_dt = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=day_offset)
                        if candidate_dt > now:
                            weekdays = sched.get("weekdays")
                            if weekdays is None or len(weekdays) == 0 or candidate_dt.weekday() in weekdays:
                                results[sched_id] = candidate_dt.isoformat()
                                break
                except Exception:
                    results[sched_id] = None

        return results

    # -------------------------------------------------------------------------
    # Déclenchement manuel immédiat (Test)
    # -------------------------------------------------------------------------
    async def async_trigger_now(self, schedule_id: str) -> bool:
        """Déclenche manuellement et immédiatement une planification."""
        sched = self.storage.get_schedule(schedule_id)
        if not sched:
            return False

        _LOGGER.info("DomoLink-Planification: Déclenchement manuel forcé de '%s'", sched.get("name", schedule_id))
        success = await self.resolver.execute_action(
            target_type=sched.get("target_type"),
            target_value=sched.get("target_value"),
            action_data=sched.get("action_data", {}),
        )

        now = dt_util.now()
        await self.storage.async_add_history({
            "timestamp": now.isoformat(),
            "schedule_id": schedule_id,
            "name": sched.get("name", schedule_id),
            "status": "MANUAL_TRIGGER" if success else "FAILED",
            "details": f"Déclenchement manuel via bouton / service",
        })
        return success
