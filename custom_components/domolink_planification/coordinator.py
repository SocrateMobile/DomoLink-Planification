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
    DEFAULT_GATE_CONFIG,
    GATE_SWITCH_TYPE_COVER,
    GATE_SWITCH_TYPE_DUAL,
    GATE_SWITCH_TYPE_PULSE,
    GATE_SWITCH_TYPE_TOGGLE,
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
        self._remove_gate_timer: Any = None
        self._gate_task: asyncio.Task | None = None
        self._gate_state: dict[str, Any] = {
            "state": "closed",
            "open_since": None,
            "target_close_time": None,
            "retries_done": 0,
            "last_action": "Initialisation",
            "last_action_time": None,
            "check_in_progress": False,
            "hold_open": False,
            "hold_open_until": None,
        }

    async def async_init(self) -> None:
        """Initialise le stockage et lance la boucle de synchronisation temporelle."""
        await self.storage.async_load()

        # Initialiser l'état du portail depuis Home Assistant
        self._init_gate_state_from_sensor()

        self.data = {
            "schedules": self.storage.get_schedules(),
            "history": self.storage.get_history(),
            "settings": self.storage.get_settings(),
            "next_runs": self.compute_all_next_runs(),
            "solar_states": self._solar_shading_states,
            "gate": self.get_gate_status(),
        }

        # Démarrer la boucle périodique de vérification des plannings (chaque 30s)
        self._remove_timer = async_track_time_interval(
            self.hass,
            self._async_tick,
            timedelta(seconds=30),
        )

        # Démarrer la boucle de rafraîchissement rapide du portail (chaque 5s)
        self._remove_gate_timer = async_track_time_interval(
            self.hass,
            self._async_gate_tick,
            timedelta(seconds=5),
        )

        # Écouteur en direct pour la présence ET pour le capteur du portail
        @callback
        def _async_on_state_changed(event: Event) -> None:
            entity_id = event.data.get("entity_id")
            if not entity_id:
                return

            # Surveillance du capteur du portail
            gate_cfg = self.storage.get_gate_config()
            sensor_id = gate_cfg.get("sensor_entity")
            if sensor_id and entity_id == sensor_id:
                old_state = event.data.get("old_state")
                new_state = event.data.get("new_state")
                if old_state and new_state and old_state.state != new_state.state:
                    self.hass.async_create_task(
                        self._async_handle_gate_sensor_change(old_state.state, new_state.state)
                    )
                return

            # Surveillance des personnes et trackers
            if entity_id.startswith("person.") or entity_id.startswith("device_tracker."):
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

        _LOGGER.info("DomoLink-Planification: Moteur de planification, présence, portail et suivi solaire démarré.")

    def async_stop(self) -> None:
        """Arrête les boucles en arrière-plan."""
        if self._remove_timer:
            self._remove_timer()
            self._remove_timer = None
        if self._remove_gate_timer:
            self._remove_gate_timer()
            self._remove_gate_timer = None
        if self._remove_state_listener:
            self._remove_state_listener()
            self._remove_state_listener = None
        if self._gate_task and not self._gate_task.done():
            self._gate_task.cancel()

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
        self.data = await self._async_update_data()
        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Méthode appelée par DataUpdateCoordinator."""
        return {
            "schedules": self.storage.get_schedules(),
            "history": self.storage.get_history(),
            "settings": self.storage.get_settings(),
            "next_runs": self.compute_all_next_runs(),
            "solar_states": self._solar_shading_states,
            "gate": self.get_gate_status(),
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

    # =========================================================================
    # GESTION DU PORTAIL & ACCÈS (Domolink-Portail)
    # =========================================================================

    def _init_gate_state_from_sensor(self) -> None:
        """Détecte l'état initial du portail depuis Home Assistant."""
        cfg = self.storage.get_gate_config()
        sensor_id = cfg.get("sensor_entity")
        if sensor_id:
            st = self.hass.states.get(sensor_id)
            if st:
                is_open = self._is_gate_open_value(st.state, cfg)
                self._gate_state["state"] = "open" if is_open else "closed"
                if is_open:
                    now = dt_util.now()
                    self._gate_state["open_since"] = now.isoformat()
                    timer_min = self._get_current_timer_minutes(cfg, now)
                    if cfg.get("enabled", True) and not cfg.get("hold_open", False):
                        self._gate_state["target_close_time"] = (now + timedelta(minutes=timer_min)).isoformat()

    def _is_gate_open_value(self, state_val: str | None, cfg: dict[str, Any]) -> bool:
        """Détermine si la valeur d'état correspond à un portail ouvert."""
        if not state_val or state_val in ("unavailable", "unknown"):
            return False
        inverted = cfg.get("sensor_inverted", False)
        val_lower = state_val.lower()
        # États standards : 'on', 'open', 'true', '1'
        standard_open = val_lower in ("on", "open", "true", "1", "opening")
        return not standard_open if inverted else standard_open

    def _get_current_timer_minutes(self, cfg: dict[str, Any], now: datetime) -> int:
        """Détermine le délai en minutes selon la plage Jour / Nuit."""
        current_time_str = now.strftime("%H:%M")
        day_start = cfg.get("day_start", "07:00")
        night_start = cfg.get("night_start", "22:00")
        if day_start <= current_time_str < night_start:
            return int(cfg.get("timer_day_minutes", 10))
        return int(cfg.get("timer_night_minutes", 3))

    def get_gate_status(self) -> dict[str, Any]:
        """Retourne l'état complet et temps réel du portail pour le frontend."""
        cfg = self.storage.get_gate_config()
        now = dt_util.now()

        # Calcul dynamique du compte à rebours en secondes
        countdown = 0
        target_iso = self._gate_state.get("target_close_time")
        if target_iso and self._gate_state.get("state") in ("open", "obstacle"):
            try:
                target_dt = datetime.fromisoformat(target_iso)
                if target_dt.tzinfo is None:
                    target_dt = dt_util.as_local(target_dt)
                diff = (target_dt - now).total_seconds()
                countdown = max(0, int(diff))
            except Exception:
                countdown = 0

        # Vérifier si le capteur physique est disponible
        sensor_id = cfg.get("sensor_entity")
        sensor_state = None
        if sensor_id:
            st = self.hass.states.get(sensor_id)
            if st:
                sensor_state = st.state

        # Déterminer la période en cours (Jour ou Nuit)
        current_time_str = now.strftime("%H:%M")
        day_start = cfg.get("day_start", "07:00")
        night_start = cfg.get("night_start", "22:00")
        is_day = day_start <= current_time_str < night_start

        return {
            "config": cfg,
            "state": self._gate_state.get("state", "closed"),
            "is_open": self._gate_state.get("state") in ("open", "obstacle", "closing", "hold_open"),
            "countdown_seconds": countdown,
            "target_close_time": target_iso,
            "open_since": self._gate_state.get("open_since"),
            "retries_done": self._gate_state.get("retries_done", 0),
            "max_retries": cfg.get("max_retries", 6),
            "last_action": self._gate_state.get("last_action", "Prêt"),
            "last_action_time": self._gate_state.get("last_action_time"),
            "hold_open": cfg.get("hold_open", False),
            "hold_open_until": cfg.get("hold_open_until"),
            "sensor_raw_state": sensor_state,
            "is_day": is_day,
            "current_timer_minutes": self._get_current_timer_minutes(cfg, now),
            "history": self.storage.get_gate_history(limit=20),
        }

    async def _async_handle_gate_sensor_change(self, old_val: str, new_val: str) -> None:
        """Gère un changement d'état du capteur physique de portail."""
        cfg = self.storage.get_gate_config()
        is_now_open = self._is_gate_open_value(new_val, cfg)
        now = dt_util.now()

        _LOGGER.info("DomoLink-Portail: Changement d'état capteur '%s' -> '%s' (is_open=%s)", old_val, new_val, is_now_open)

        if is_now_open:
            self._gate_state["open_since"] = now.isoformat()
            self._gate_state["last_action"] = "Ouverture détectée"
            self._gate_state["last_action_time"] = now.isoformat()

            # Si maintien ouvert actif
            if cfg.get("hold_open", False):
                self._gate_state["state"] = "hold_open"
                self._gate_state["target_close_time"] = None
                await self.storage.async_add_gate_history({
                    "timestamp": now.isoformat(),
                    "event": "OUVERTURE",
                    "status": "HOLD_OPEN",
                    "details": "Portail ouvert (mode maintien activé, fermeture auto suspendue)",
                })
            elif cfg.get("enabled", True):
                timer_min = self._get_current_timer_minutes(cfg, now)
                target = now + timedelta(minutes=timer_min)
                self._gate_state["state"] = "open"
                self._gate_state["target_close_time"] = target.isoformat()
                self._gate_state["retries_done"] = 0
                await self.storage.async_add_gate_history({
                    "timestamp": now.isoformat(),
                    "event": "OUVERTURE",
                    "status": "TIMER_STARTED",
                    "details": f"Portail ouvert (fermeture automatique programmée dans {timer_min} min)",
                })
        else:
            # Le portail est fermé
            self._gate_state["state"] = "closed"
            self._gate_state["target_close_time"] = None
            self._gate_state["retries_done"] = 0
            self._gate_state["open_since"] = None
            self._gate_state["last_action"] = "Fermeture confirmée"
            self._gate_state["last_action_time"] = now.isoformat()
            await self.storage.async_add_gate_history({
                "timestamp": now.isoformat(),
                "event": "FERMETURE",
                "status": "CLOSED",
                "details": "Portail fermé et sécurisé",
            })

        self.data["gate"] = self.get_gate_status()
        self.async_set_updated_data(self.data)

    async def _async_gate_tick(self, now: datetime) -> None:
        """Vérification rapide (toutes les 5s) pour le décompte et l'auto-fermeture."""
        cfg = self.storage.get_gate_config()
        now_local = dt_util.as_local(now)

        # 1. Vérifier l'expiration du maintien ouvert temporisé
        hold_until_str = cfg.get("hold_open_until")
        if hold_until_str:
            try:
                hold_until_dt = datetime.fromisoformat(hold_until_str)
                if hold_until_dt.tzinfo is None:
                    hold_until_dt = dt_util.as_local(hold_until_dt)
                if now_local >= hold_until_dt:
                    _LOGGER.info("DomoLink-Portail: Expiration du maintien ouvert temporisé")
                    await self.async_gate_set_hold_open(False)
            except Exception as err:
                _LOGGER.debug("Erreur parsing hold_open_until: %s", err)

        # 2. Vérifier si l'échéance de fermeture automatique est arrivée
        target_iso = self._gate_state.get("target_close_time")
        if (
            target_iso
            and cfg.get("enabled", True)
            and not cfg.get("hold_open", False)
            and not self._gate_state.get("check_in_progress", False)
            and self._gate_state.get("state") in ("open", "obstacle")
        ):
            try:
                target_dt = datetime.fromisoformat(target_iso)
                if target_dt.tzinfo is None:
                    target_dt = dt_util.as_local(target_dt)
                if now_local >= target_dt:
                    # Lancer le cycle de fermeture en tâche asynchrone non-bloquante
                    self._gate_state["target_close_time"] = None
                    if self._gate_task and not self._gate_task.done():
                        self._gate_task.cancel()
                    self._gate_task = self.hass.async_create_task(self.async_gate_close_cycle())
            except Exception as err:
                _LOGGER.error("DomoLink-Portail: Erreur tick fermeture auto: %s", err)

        # 3. Rafraîchir l'état du portail pour le frontend
        self.data["gate"] = self.get_gate_status()
        self.async_set_updated_data(self.data)

    async def async_gate_close_cycle(self) -> None:
        """Exécute le cycle complet : notification préalable, impulsion, vérification et réessais."""
        cfg = self.storage.get_gate_config()
        max_retries = int(cfg.get("max_retries", 6))
        check_delay = int(cfg.get("check_delay", 60))
        retry_interval = int(cfg.get("retry_interval_minutes", 10))

        self._gate_state["check_in_progress"] = True
        self._gate_state["state"] = "closing"
        current_retry = self._gate_state.get("retries_done", 0) + 1
        now = dt_util.now()

        _LOGGER.info("DomoLink-Portail: Démarrage cycle fermeture (Essai %d/%d)", current_retry, max_retries)

        # 1. Envoi SMS d'avertissement
        await self._async_send_gate_notification(
            f"[Portail] Portail resté ouvert. Lancement de la fermeture automatique (Tentative {current_retry}/{max_retries})."
        )

        # 2. Actionner la commande de fermeture selon le type
        await self.async_gate_trigger_action(mode="close")

        self._gate_state["last_action"] = f"Action de fermeture envoyée (Tentative {current_retry}/{max_retries})"
        self._gate_state["last_action_time"] = now.isoformat()
        self.data["gate"] = self.get_gate_status()
        self.async_set_updated_data(self.data)

        # 3. Attente du temps de manœuvre (ex: 60 secondes)
        await asyncio.sleep(check_delay)

        # 4. Vérification de l'état réel du capteur
        sensor_id = cfg.get("sensor_entity")
        is_still_open = True
        if sensor_id:
            st = self.hass.states.get(sensor_id)
            if st:
                is_still_open = self._is_gate_open_value(st.state, cfg)

        now_after = dt_util.now()

        if not is_still_open:
            # Succès : Le portail est bien fermé
            self._gate_state["state"] = "closed"
            self._gate_state["retries_done"] = 0
            self._gate_state["check_in_progress"] = False
            self._gate_state["target_close_time"] = None
            self._gate_state["last_action"] = "Fermeture réussie confirmée"
            self._gate_state["last_action_time"] = now_after.isoformat()

            await self._async_send_gate_notification("[Portail] Le portail est maintenant bien fermé.")
            await self.storage.async_add_gate_history({
                "timestamp": now_after.isoformat(),
                "event": "FERMETURE_AUTO",
                "status": "SUCCESS",
                "details": f"Fermeture automatique réussie à la tentative {current_retry}/{max_retries}",
            })
        else:
            # Échec : Le portail est toujours ouvert (obstacle / blocage)
            self._gate_state["retries_done"] = current_retry
            self._gate_state["check_in_progress"] = False

            if current_retry < max_retries:
                # Alerte obstacle et programmation du réessai dans X minutes
                self._gate_state["state"] = "obstacle"
                self._gate_state["target_close_time"] = (now_after + timedelta(minutes=retry_interval)).isoformat()
                self._gate_state["last_action"] = f"Obstacle détecté (Essai {current_retry}/{max_retries})"
                self._gate_state["last_action_time"] = now_after.isoformat()

                await self._async_send_gate_notification(
                    f"[Alerte Portail] Échec de fermeture (obstacle ou blocage détecté). Prochaine tentative dans {retry_interval} min (essai {current_retry}/{max_retries})."
                )
                await self.storage.async_add_gate_history({
                    "timestamp": now_after.isoformat(),
                    "event": "OBSTACLE",
                    "status": "RETRY_SCHEDULED",
                    "details": f"Obstacle détecté, réessai {current_retry + 1}/{max_retries} dans {retry_interval} min",
                })
            else:
                # Échec final après max_retries : Alerte critique
                self._gate_state["state"] = "obstacle"
                self._gate_state["target_close_time"] = None
                self._gate_state["last_action"] = f"URGENT: Échec après {max_retries} tentatives"
                self._gate_state["last_action_time"] = now_after.isoformat()

                await self._async_send_gate_notification(
                    f"[URGENT] Le portail est toujours OUVERT après {max_retries} tentatives. Intervention manuelle requise !"
                )
                await self.storage.async_add_gate_history({
                    "timestamp": now_after.isoformat(),
                    "event": "ECHEC_CRITIQUE",
                    "status": "FAILED",
                    "details": f"Arrêt d'urgence des fermetures automatiques après {max_retries} tentatives",
                })

        self.data["gate"] = self.get_gate_status()
        self.async_set_updated_data(self.data)

    async def async_gate_trigger_action(self, mode: str = "toggle") -> bool:
        """Déclenche la commande matérielle du portail selon le type d'interrupteur configuré."""
        cfg = self.storage.get_gate_config()
        switch_type = cfg.get("switch_type", GATE_SWITCH_TYPE_PULSE)
        switch_entity = cfg.get("switch_entity")
        close_switch_entity = cfg.get("close_switch_entity")
        pulse_duration = float(cfg.get("pulse_duration", 1.0))

        if not switch_entity:
            _LOGGER.warning("DomoLink-Portail: Aucun switch configuré pour commander le portail")
            return False

        try:
            if switch_type == GATE_SWITCH_TYPE_PULSE:
                # Contact sec / impulsion
                domain = switch_entity.split(".")[0]
                await self.hass.services.async_call(domain, "turn_on", {"entity_id": switch_entity}, blocking=True)
                if pulse_duration > 0:
                    await asyncio.sleep(pulse_duration)
                    # Sécurité auto-off si le relais ne le gère pas en interne
                    st = self.hass.states.get(switch_entity)
                    if st and st.state == "on":
                        await self.hass.services.async_call(domain, "turn_off", {"entity_id": switch_entity}, blocking=True)

            elif switch_type == GATE_SWITCH_TYPE_DUAL:
                # Deux commandes séparées
                target_entity = close_switch_entity if mode == "close" and close_switch_entity else switch_entity
                domain = target_entity.split(".")[0]
                await self.hass.services.async_call(domain, "turn_on", {"entity_id": target_entity}, blocking=True)
                if pulse_duration > 0:
                    await asyncio.sleep(pulse_duration)
                    st = self.hass.states.get(target_entity)
                    if st and st.state == "on":
                        await self.hass.services.async_call(domain, "turn_off", {"entity_id": target_entity}, blocking=True)

            elif switch_type == GATE_SWITCH_TYPE_COVER:
                # Entité Cover native
                if mode == "close":
                    await self.hass.services.async_call("cover", "close_cover", {"entity_id": switch_entity}, blocking=True)
                elif mode == "open":
                    await self.hass.services.async_call("cover", "open_cover", {"entity_id": switch_entity}, blocking=True)
                else:
                    await self.hass.services.async_call("cover", "toggle", {"entity_id": switch_entity}, blocking=True)

            elif switch_type == GATE_SWITCH_TYPE_TOGGLE:
                # Interrupteur bistable ON/OFF
                domain = switch_entity.split(".")[0]
                action = "turn_off" if mode == "close" else "turn_on"
                await self.hass.services.async_call(domain, action, {"entity_id": switch_entity}, blocking=True)

            return True
        except Exception as err:
            _LOGGER.error("DomoLink-Portail: Erreur lors de la commande du portail (%s): %s", switch_type, err)
            return False

    async def async_gate_set_hold_open(self, enabled: bool, duration_minutes: int | None = None) -> None:
        """Active ou désactive le mode maintien ouvert (permanent ou temporisé)."""
        cfg = self.storage.get_gate_config()
        now = dt_util.now()

        hold_until_iso = None
        if enabled and duration_minutes and duration_minutes > 0:
            hold_until_iso = (now + timedelta(minutes=duration_minutes)).isoformat()

        cfg["hold_open"] = enabled
        cfg["hold_open_until"] = hold_until_iso
        await self.storage.async_update_gate_config(cfg)

        if enabled:
            self._gate_state["target_close_time"] = None
            if self._gate_state.get("state") == "open":
                self._gate_state["state"] = "hold_open"
            desc = f"Maintien ouvert activé ({duration_minutes} min)" if duration_minutes else "Maintien ouvert permanent activé"
        else:
            desc = "Maintien ouvert désactivé"
            # Si le portail est actuellement ouvert, relancer le timer
            sensor_id = cfg.get("sensor_entity")
            if sensor_id:
                st = self.hass.states.get(sensor_id)
                if st and self._is_gate_open_value(st.state, cfg):
                    timer_min = self._get_current_timer_minutes(cfg, now)
                    self._gate_state["state"] = "open"
                    self._gate_state["target_close_time"] = (now + timedelta(minutes=timer_min)).isoformat()

        await self.storage.async_add_gate_history({
            "timestamp": now.isoformat(),
            "event": "MAINTIEN_OUVERT",
            "status": "ON" if enabled else "OFF",
            "details": desc,
        })

        self.data["gate"] = self.get_gate_status()
        self.async_set_updated_data(self.data)

    async def _async_send_gate_notification(self, message: str) -> None:
        """Envoie une notification via le service configuré (Free SMS, HA Companion, etc.)."""
        cfg = self.storage.get_gate_config()
        notify_service = cfg.get("notify_service")
        if not notify_service:
            return

        _LOGGER.info("DomoLink-Portail: Envoi notification -> %s : %s", notify_service, message)
        try:
            # Cas 1 : notify.send_message avec entity_id cible
            if notify_service.startswith("notify."):
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"entity_id": notify_service, "message": message},
                    blocking=True,
                )
            else:
                # Cas 2 : appel de service direct (ex: free_mobile_sms)
                domain = "notify"
                service_name = notify_service.replace("notify.", "")
                await self.hass.services.async_call(
                    domain,
                    service_name,
                    {"message": message},
                    blocking=True,
                )
        except Exception as err:
            _LOGGER.debug("Erreur send_message, tentative via service direct: %s", err)
            try:
                domain = "notify"
                service_name = notify_service.replace("notify.", "")
                await self.hass.services.async_call(
                    domain,
                    service_name,
                    {"message": message},
                    blocking=True,
                )
            except Exception as fallback_err:
                _LOGGER.error("DomoLink-Portail: Échec d'envoi notification (%s): %s", notify_service, fallback_err)

