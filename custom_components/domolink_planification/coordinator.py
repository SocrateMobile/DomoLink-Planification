"""Coordinateur central et moteur d'exécution pour DomoLink-Planification."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
import random
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DATE_MODE_EXACT_DAY,
    DATE_MODE_WEEKDAYS,
    DOMAIN,
    HOLIDAY_MODE_ALWAYS,
    HOLIDAY_MODE_EXCLUDE,
    HOLIDAY_MODE_ONLY,
    HOLIDAY_MODE_WEEKEND,
    POST_EXEC_ACTION_DELETE,
    POST_EXEC_ACTION_DISABLE,
    RECURRENCE_DATE,
    RECURRENCE_EVERY,
    RECURRENCE_NEXT,
    REMINDER_CHANNEL_APP,
    TARGET_TYPE_REMINDER,
    TIME_TYPE_FIXED,
    TIME_TYPE_SUNRISE,
    TIME_TYPE_SUNSET,
    TIME_TYPE_ZONE_ENTER,
    TIME_TYPE_ZONE_LEAVE,
    TRIGGER_TYPE_INTERVAL,
    TRIGGER_TYPE_ONCE,
    TRIGGER_TYPE_SOLAR,
    TRIGGER_TYPE_SOLAR_SHADING,
    TRIGGER_TYPE_TIME,
)
from .holidays import HolidayEngine
from .recurrence import RecurrenceEngine
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
        self._remove_state_listener: Any = None

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

        # Écouteur en direct des arrivées et départs de zones pour les personnes et trackers
        @callback
        def _async_on_state_changed(event: Event) -> None:
            entity_id = event.data.get("entity_id")
            if not entity_id or not (entity_id.startswith("person.") or entity_id.startswith("device_tracker.")):
                return
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            if not old_state or not new_state or old_state.state == new_state.state:
                return
            self.hass.async_create_task(
                self._async_handle_person_state_change(entity_id, old_state.state, new_state.state)
            )

        self._remove_state_listener = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED,
            _async_on_state_changed,
        )

        _LOGGER.info("DomoLink-Planification: Moteur de planification, présence et suivi solaire démarré.")

    def async_stop(self) -> None:
        """Arrête les boucles en arrière-plan."""
        if self._remove_timer:
            self._remove_timer()
            self._remove_timer = None
        if self._remove_state_listener:
            self._remove_state_listener()
            self._remove_state_listener = None

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
            if not sched.get("enabled", True) or sched.get("is_completed", False):
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
            action_data = dict(sched.get("action_data", {}))
            if sched.get("target_type") == TARGET_TYPE_REMINDER:
                action_data["reminder_message"] = sched.get("reminder_message") or sched.get("target_value")
                action_data["channel"] = sched.get("reminder_channel") or REMINDER_CHANNEL_APP

            success = await self.resolver.execute_action(
                target_type=sched.get("target_type"),
                target_value=sched.get("target_value"),
                action_data=action_data,
            )

            # Enregistrer dans l'historique
            await self.storage.async_add_history({
                "timestamp": now.isoformat(),
                "schedule_id": sched_id,
                "name": sched.get("name", sched_id),
                "status": "SUCCESS" if success else "FAILED",
                "details": f"Cible: {sched.get('target_type')} ({sched.get('target_value')})",
            })

            # Gestion post-exécution selon le mode de récurrence (Option B: Supprimer ou Désactiver)
            recurrence_mode = sched.get("recurrence_mode", RECURRENCE_EVERY)
            post_action = sched.get("post_execution_action", POST_EXEC_ACTION_DISABLE)

            if recurrence_mode == RECURRENCE_NEXT or trigger_type == TRIGGER_TYPE_ONCE:
                if post_action == POST_EXEC_ACTION_DELETE:
                    _LOGGER.info("DomoLink-Planification: Suppression automatique de '%s' après exécution", sched.get("name"))
                    await self.storage.async_delete_schedule(sched_id)
                else:
                    sched["enabled"] = False
                    sched["is_completed"] = True
                    await self.storage.async_save_schedule(sched_id, sched)

            elif recurrence_mode == RECURRENCE_DATE:
                year_val = sched.get("year")
                date_mode = sched.get("date_selection_type", DATE_MODE_EXACT_DAY)
                # Si année fixe et jour unique : marquer comme terminé ou supprimer
                if year_val != "every_year" and date_mode == DATE_MODE_EXACT_DAY:
                    if post_action == POST_EXEC_ACTION_DELETE:
                        _LOGGER.info("DomoLink-Planification: Suppression de la règle de date '%s' après exécution", sched.get("name"))
                        await self.storage.async_delete_schedule(sched_id)
                    else:
                        sched["enabled"] = False
                        sched["is_completed"] = True
                        await self.storage.async_save_schedule(sched_id, sched)

    # -------------------------------------------------------------------------
    # Gestion des déclencheurs de présence géographique (Arrivée / Sortie zone)
    # -------------------------------------------------------------------------
    def _matches_zone(self, zone_id: str, state_str: str) -> bool:
        """Vérifie si un état correspond à une zone donnée."""
        if not state_str:
            return False
        st_clean = state_str.strip().lower()

        # 1. zone.home / Maison
        if zone_id in ("zone.home", "home"):
            return st_clean in ("home", "maison")

        clean_zone = zone_id if zone_id.startswith("zone.") else f"zone.{zone_id}"
        zone_ent = self.hass.states.get(clean_zone)
        if zone_ent:
            friendly = (zone_ent.attributes.get("friendly_name") or "").strip().lower()
            if friendly and st_clean == friendly:
                return True
            if st_clean == zone_ent.name.strip().lower():
                return True

        short_name = clean_zone.replace("zone.", "").strip().lower()
        if st_clean == short_name:
            return True

        return False

    def _is_zone_transition_match(self, target_zone_id: str, old_st: str, new_st: str, time_type: str) -> bool:
        """Détermine si la transition d'état correspond à l'entrée ou la sortie de la zone."""
        was_in = self._matches_zone(target_zone_id, old_st)
        is_in = self._matches_zone(target_zone_id, new_st)

        if time_type == TIME_TYPE_ZONE_ENTER:
            return (not was_in) and is_in
        if time_type == TIME_TYPE_ZONE_LEAVE:
            return was_in and (not is_in)
        return False

    async def _async_handle_person_state_change(self, person_id: str, old_st: str, new_st: str) -> None:
        """Gère le déclenchement des règles de présence (Entrée / Sortie de zone)."""
        now = dt_util.now()
        schedules = self.storage.get_schedules()
        settings = self.storage.get_settings()
        country = settings.get("country", "FR")

        for sched_id, sched in list(schedules.items()):
            if not sched.get("enabled", True) or sched.get("is_completed", False):
                continue

            time_type = sched.get("time_type")
            if time_type not in (TIME_TYPE_ZONE_ENTER, TIME_TYPE_ZONE_LEAVE):
                continue

            # 1. Vérification de la personne
            target_person = sched.get("zone_person_id")
            if target_person and target_person not in ("any", "all", "") and target_person != person_id:
                continue

            # 2. Résolution de la zone cible
            target_zone_id = sched.get("zone_id", "zone.home")
            if not self._is_zone_transition_match(target_zone_id, old_st, new_st, time_type):
                continue

            # 3. Vérification de la récurrence (jours autorisés, date, etc.)
            if not RecurrenceEngine.check_date_match(sched, now):
                continue

            # 4. Vérification des conditions de garde-fous (Jours fériés, alarme, etc.)
            condition_met, cond_reason = self._check_conditions(sched, now, country)
            if not condition_met:
                _LOGGER.info("DomoLink-Planification [Zone %s] Ignoré pour %s : %s", sched.get("name"), person_id, cond_reason)
                await self.storage.async_add_history({
                    "timestamp": now.isoformat(),
                    "schedule_id": sched_id,
                    "name": sched.get("name", sched_id),
                    "status": "SKIPPED",
                    "details": f"Zone: {cond_reason}",
                })
                continue

            # 5. Déclenchement de l'action !
            _LOGGER.info("DomoLink-Planification [Zone %s] Déclenchement pour %s (%s -> %s)", sched.get("name"), person_id, old_st, new_st)
            action_data = dict(sched.get("action_data", {}))
            if sched.get("target_type") == TARGET_TYPE_REMINDER:
                action_data["reminder_message"] = sched.get("reminder_message") or sched.get("target_value")
                action_data["channel"] = sched.get("reminder_channel") or REMINDER_CHANNEL_APP

            success = await self.resolver.execute_action(
                target_type=sched.get("target_type"),
                target_value=sched.get("target_value"),
                action_data=action_data,
            )

            # 6. Historique
            event_name = "Arrivée" if time_type == TIME_TYPE_ZONE_ENTER else "Sortie"
            await self.storage.async_add_history({
                "timestamp": now.isoformat(),
                "schedule_id": sched_id,
                "name": sched.get("name", sched_id),
                "status": "SUCCESS" if success else "FAILED",
                "details": f"{event_name} de {person_id} ({target_zone_id})",
            })

            # 7. Post-exécution (Option B: Supprimer ou Désactiver si 'next' ou ponctuel)
            recurrence_mode = sched.get("recurrence_mode", RECURRENCE_EVERY)
            post_action = sched.get("post_execution_action", POST_EXEC_ACTION_DISABLE)
            if recurrence_mode == RECURRENCE_NEXT:
                if post_action == POST_EXEC_ACTION_DELETE:
                    await self.storage.async_delete_schedule(sched_id)
                else:
                    sched["enabled"] = False
                    sched["is_completed"] = True
                    await self.storage.async_save_schedule(sched_id, sched)

    def _check_trigger_match(self, sched: dict[str, Any], now: datetime) -> bool:
        """Vérifie si l'heure et la date courantes correspondent au déclencheur."""
        time_type = sched.get("time_type", TIME_TYPE_FIXED)
        trigger_type = sched.get("trigger_type", TRIGGER_TYPE_TIME)
        sun_target_time = None

        if time_type in (TIME_TYPE_SUNRISE, TIME_TYPE_SUNSET) or trigger_type == TRIGGER_TYPE_SOLAR:
            solar_event = sched.get("solar_event") or ("sunrise" if time_type == TIME_TYPE_SUNRISE else "sunset")
            offset_minutes = int(sched.get("solar_offset_minutes", 0))

            sun_state = self.hass.states.get("sun.sun")
            if sun_state:
                attr_key = "next_rising" if solar_event == "sunrise" else "next_setting"
                event_iso = sun_state.attributes.get(attr_key)
                if event_iso:
                    try:
                        event_dt = dt_util.parse_datetime(event_iso)
                        if event_dt:
                            sun_target_time = dt_util.as_local(event_dt) + timedelta(minutes=offset_minutes)
                    except Exception:
                        pass

        return RecurrenceEngine.check_trigger_match(sched, now, sun_target_time)

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
            if not sched.get("enabled", True) or sched.get("is_completed", False):
                results[sched_id] = None
                continue

            t_type = sched.get("trigger_type", TRIGGER_TYPE_TIME)
            time_type = sched.get("time_type")
            if t_type == TRIGGER_TYPE_SOLAR_SHADING:
                results[sched_id] = "Continu (Suivi solaire)"
                continue

            if time_type in (TIME_TYPE_ZONE_ENTER, TIME_TYPE_ZONE_LEAVE):
                z_id = sched.get("zone_id", "zone.home")
                z_st = self.hass.states.get(z_id)
                z_name = (z_st.attributes.get("friendly_name") or z_st.name) if z_st else z_id.replace("zone.", "").capitalize()
                p_id = sched.get("zone_person_id")
                p_name = "Toute personne"
                if p_id and p_id not in ("any", "all", ""):
                    p_st = self.hass.states.get(p_id)
                    p_name = (p_st.attributes.get("friendly_name") or p_st.name) if p_st else p_id

                if time_type == TIME_TYPE_ZONE_ENTER:
                    results[sched_id] = f"📍 Arrivée ({p_name} ➔ {z_name})"
                else:
                    results[sched_id] = f"🚪 Sortie ({p_name} ➔ {z_name})"
                continue

            if t_type == TRIGGER_TYPE_ONCE:
                results[sched_id] = sched.get("target_datetime")
                continue

            results[sched_id] = RecurrenceEngine.compute_next_run(sched, now)

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
