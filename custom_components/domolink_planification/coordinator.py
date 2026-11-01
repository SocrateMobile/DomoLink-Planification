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
    CONF_DEFAULT_COUNTRY,
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
    TARGET_TYPE_GATE,
    TARGET_TYPE_LABEL,
    TARGET_TYPE_REMINDER,
    TIME_TYPE_FIXED,
    TIME_TYPE_SUNRISE,
    TIME_TYPE_SUNSET,
    TIME_TYPE_ZONE_ENTER,
    TIME_TYPE_ZONE_LEAVE,
    VACATION_MODE_ALWAYS,
    VACATION_MODE_EXCLUDE,
    VACATION_MODE_ONLY,
    WEATHER_COND_ANY,
    WEATHER_COND_NO_RAIN,
    WEATHER_COND_SUNNY,
    DEFAULT_GATE_CONFIG,
    GATE_TYPE_SLIDING,
    GATE_TYPE_DOUBLE_SWING,
    GATE_TYPE_SINGLE_SWING,
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
from .automation_engine import AutomationEngine
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
        self.automation_engine = AutomationEngine(hass, storage, self.resolver, coordinator=self)
        self.solar_shading = SolarShadingEvaluator(hass)

        self._last_evaluated_minute: str | None = None
        self._solar_shading_states: dict[str, dict[str, Any]] = {}
        self._remove_timer: Any = None
        self._remove_state_listener: Any = None
        self._remove_gate_timer: Any = None
        self._gate_tasks: dict[str, asyncio.Task] = {}
        self._gate_opening_tasks: dict[str, asyncio.Task] = {}
        self._gate_states: dict[str, dict[str, Any]] = {}

    @property
    def _gate_state(self) -> dict[str, Any]:
        """Accès rétrocompatible à l'état du portail principal."""
        gates = self.storage.get_gates()
        first_id = next(iter(gates)) if gates else "gate_1"
        return self._get_gate_internal_state(first_id)

    def _get_gate_internal_state(self, gate_id: str = "gate_1") -> dict[str, Any]:
        """Retourne ou initialise l'état mémoire d'un portail/accès."""
        if gate_id not in self._gate_states:
            self._gate_states[gate_id] = {
                "state": "closed",
                "open_since": None,
                "target_close_time": None,
                "retries_done": 0,
                "last_action": "Initialisation",
                "last_action_time": None,
                "check_in_progress": False,
                "hold_open": False,
                "hold_open_until": None,
                "movement_start": None,
            }
        return self._gate_states[gate_id]


    async def async_init(self) -> None:
        """Initialise le stockage et lance la boucle de synchronisation temporelle."""
        await self.storage.async_load()

        # Initialiser l'état du portail depuis Home Assistant
        self._init_gate_state_from_sensor()

        # Démarrer le moteur d'automatisations modernes
        await self.automation_engine.async_start()

        self.data = {
            "schedules": self.storage.get_schedules(),
            "history": self.storage.get_history(),
            "settings": self.storage.get_settings(),
            "next_runs": self.compute_all_next_runs(),
            "solar_states": self._solar_shading_states,
            "gate": self.get_gate_status(),
            "gates": self.get_all_gates_status(),
            "automations": self.storage.get_automations(),
            "automation_traces": self.storage.get_automation_traces(),
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

            # Surveillance des capteurs de tous les accès (portails, portes, garages)
            gates = self.storage.get_gates()
            for gid, gcfg in gates.items():
                sensor_id = gcfg.get("sensor_entity")
                if not sensor_id:
                    continue
                is_target_sensor = False
                if entity_id == sensor_id:
                    is_target_sensor = True
                elif sensor_id.startswith("label:"):
                    resolved = self.resolver.resolve_entities(TARGET_TYPE_LABEL, sensor_id[6:])
                    if entity_id in resolved:
                        is_target_sensor = True

                if is_target_sensor:
                    old_state = event.data.get("old_state")
                    new_state = event.data.get("new_state")
                    if old_state and new_state and old_state.state != new_state.state:
                        self.hass.async_create_task(
                            self._async_handle_gate_sensor_change(old_state.state, new_state.state, gate_id=gid)
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
        self.automation_engine.async_stop()
        if self._remove_timer:
            self._remove_timer()
            self._remove_timer = None
        if self._remove_gate_timer:
            self._remove_gate_timer()
            self._remove_gate_timer = None
        if self._remove_state_listener:
            self._remove_state_listener()
            self._remove_state_listener = None
        for task in self._gate_tasks.values():
            if task and not task.done():
                task.cancel()
        for task in self._gate_opening_tasks.values():
            if task and not task.done():
                task.cancel()

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
        labels_list = []
        try:
            from homeassistant.helpers import label_registry as lr
            label_reg = lr.async_get(self.hass)
            for lbl in label_reg.labels.values():
                labels_list.append({
                    "id": lbl.label_id,
                    "name": lbl.name,
                    "icon": lbl.icon or "mdi:tag-outline",
                    "color": lbl.color or "blue",
                })
        except Exception as err:
            _LOGGER.debug("Erreur lecture label_registry: %s", err)

        return {
            "schedules": self.storage.get_schedules(),
            "history": self.storage.get_history(),
            "settings": self.storage.get_settings(),
            "next_runs": self.compute_all_next_runs(),
            "solar_states": self._solar_shading_states,
            "gate": self.get_gate_status(),
            "gates": self.get_all_gates_status(),
            "labels": labels_list,

            "automations": self.storage.get_automations(),
            "automation_traces": self.storage.get_automation_traces(),
        }

    # -------------------------------------------------------------------------
    # Évaluation des règles de suivi solaire (Volets)
    # -------------------------------------------------------------------------
    def clear_solar_override(self, schedule_id: str) -> None:
        """Efface la dérogation manuelle d'une règle solaire pour reprendre l'automatisme immédiatement."""
        st = self._solar_shading_states.get(schedule_id)
        if st:
            st["manual_override"] = False
            st["override_until"] = None
            st["last_commanded_pos"] = None
            st["should_shade"] = None

    async def _evaluate_solar_shading_rules(self, now: datetime) -> None:
        """Parcourt les règles de type suivi solaire et positionne les volets."""
        schedules = self.storage.get_schedules()
        settings = self.storage.get_settings()
        for sched_id, sched in schedules.items():
            if not sched.get("enabled", True):
                continue
            if sched.get("trigger_type") != TRIGGER_TYPE_SOLAR_SHADING:
                continue

            last_state = self._solar_shading_states.get(sched_id)
            eval_result = self.solar_shading.evaluate_rule(
                sched,
                last_action_state=last_state,
                settings=settings,
                now=now,
            )
            self._solar_shading_states[sched_id] = eval_result

            # Si une action est requise (changement de position nécessaire)
            if eval_result.get("should_act"):
                cover_id = eval_result.get("cover_entity_id")
                target_pos = eval_result.get("target_position")
                reason = eval_result.get("reason", "")

                if cover_id and target_pos is not None:
                    # Résolution d'étiquette (label:) ou entité directe
                    if str(cover_id).startswith("label:"):
                        target_covers = [
                            eid for eid in self.resolver.resolve_entities(TARGET_TYPE_LABEL, str(cover_id)[6:])
                            if eid.startswith("cover.")
                        ]
                    else:
                        target_covers = [cover_id]

                    if not target_covers:
                        continue

                    _LOGGER.info("DomoLink-Planification [Volet Solaire] %s : %s", target_covers, reason)
                    try:
                        await self.hass.services.async_call(
                            "cover",
                            "set_cover_position",
                            {"entity_id": target_covers, "position": target_pos},
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
                        _LOGGER.error("Erreur commande volet %s : %s", target_covers, err)

    # -------------------------------------------------------------------------
    # Évaluation des règles temporelles (Heure, Solaire, Ponctuel, Intervalle)
    # -------------------------------------------------------------------------
    async def _evaluate_time_rules(self, now: datetime) -> None:
        """Vérifie si des règles temporelles doivent se déclencher à la minute courante."""
        schedules = self.storage.get_schedules()
        settings = self.storage.get_settings()
        default_country = "FR"
        if hasattr(self, "entry") and self.entry:
            default_country = self.entry.options.get(CONF_DEFAULT_COUNTRY, self.entry.data.get(CONF_DEFAULT_COUNTRY, "FR"))
        country = settings.get("country") or default_country

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
            success = await self._execute_schedule_action(sched)

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
            success = await self._execute_schedule_action(sched)

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

            try:
                from homeassistant.helpers.sun import get_astral_event_date
                from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
                event_name = SUN_EVENT_SUNRISE if solar_event == "sunrise" else SUN_EVENT_SUNSET
                solar_dt = get_astral_event_date(self.hass, event_name, now.date())
                if solar_dt:
                    sun_target_time = dt_util.as_local(solar_dt) + timedelta(minutes=offset_minutes)
            except Exception:
                sun_target_time = None

            if sun_target_time is None:
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

        # 4. Mode Vacances / Simulation de présence
        sched_vac = sched.get("vacation_mode", VACATION_MODE_ALWAYS)
        is_vacation = bool(self.storage.get_settings().get("vacation_mode", False))
        if sched_vac == VACATION_MODE_ONLY and not is_vacation:
            return False, "Exécuté uniquement lorsque le Mode Vacances est actif"
        if sched_vac == VACATION_MODE_EXCLUDE and is_vacation:
            return False, "Suspendu pendant le Mode Vacances"

        # 5. Condition Météo (ex: Pas de pluie pour arrosage / extérieur)
        w_cond = sched.get("weather_condition", WEATHER_COND_ANY)
        if w_cond and w_cond != WEATHER_COND_ANY:
            w_entity = sched.get("weather_entity") or self.storage.get_settings().get("solar_weather_entity")
            if not w_entity or not str(w_entity).startswith("weather."):
                for st_obj in self.hass.states.async_all("weather"):
                    w_entity = st_obj.entity_id
                    break
            if w_entity:
                w_state = self.hass.states.get(w_entity)
                if w_state and w_state.state not in ("unknown", "unavailable"):
                    st_val = str(w_state.state).lower()
                    rain_states = {"rainy", "pouring", "lightning-rainy", "hail", "snowy", "snowy-rainy"}
                    sunny_states = {"sunny", "clear-night", "partlycloudy"}
                    if w_cond == WEATHER_COND_NO_RAIN and st_val in rain_states:
                        return False, f"Météo pluvieuse/intempéries ({st_val}) ➔ action annulée"
                    if w_cond == WEATHER_COND_SUNNY and st_val not in sunny_states:
                        return False, f"Météo non ensoleillée ({st_val}) ➔ action annulée"

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
    # Exécution d'action de planification & Déclenchement manuel immédiat
    # -------------------------------------------------------------------------
    async def _execute_schedule_action(self, sched: dict[str, Any]) -> bool:
        """Exécute la cible d'une planification (incluant le contrôle natif d'accès DomoLink)."""
        target_type = sched.get("target_type")
        target_value = sched.get("target_value")
        action_data = dict(sched.get("action_data", {}))

        if target_type == TARGET_TYPE_GATE:
            gate_id = target_value or action_data.get("gate_id") or "gate_1"
            operation = action_data.get("gate_operation") or action_data.get("service") or "toggle"
            if operation in ("toggle", "trigger"):
                return await self.async_gate_trigger_action(mode="toggle", gate_id=gate_id)
            elif operation in ("open", "open_now"):
                return await self.async_gate_trigger_action(mode="open", gate_id=gate_id)
            elif operation in ("close", "close_now"):
                return await self.async_gate_trigger_action(mode="close", gate_id=gate_id)
            elif operation == "pedestrian":
                return await self.async_gate_trigger_action(mode="pedestrian", gate_id=gate_id)
            elif operation == "hold_open":
                dur = int(action_data.get("duration_minutes") or 60)
                await self.async_gate_set_hold_open(True, duration_minutes=dur, gate_id=gate_id)
                return True
            elif operation == "cancel_hold_open":
                await self.async_gate_set_hold_open(False, gate_id=gate_id)
                return True
            return await self.async_gate_trigger_action(mode="toggle", gate_id=gate_id)

        if target_type == TARGET_TYPE_REMINDER:
            action_data["reminder_message"] = sched.get("reminder_message") or target_value
            action_data["channel"] = sched.get("reminder_channel") or REMINDER_CHANNEL_APP

        return await self.resolver.execute_action(
            target_type=target_type,
            target_value=target_value,
            action_data=action_data,
        )

    async def async_trigger_now(self, schedule_id: str) -> bool:
        """Déclenche manuellement et immédiatement une planification."""
        sched = self.storage.get_schedule(schedule_id)
        if not sched:
            return False

        _LOGGER.info("DomoLink-Planification: Déclenchement manuel forcé de '%s'", sched.get("name", schedule_id))
        success = await self._execute_schedule_action(sched)

        now = dt_util.now()
        await self.storage.async_add_history({
            "timestamp": now.isoformat(),
            "schedule_id": schedule_id,
            "name": sched.get("name", schedule_id),
            "status": "MANUAL_TRIGGER" if success else "FAILED",
            "details": "Déclenchement manuel via bouton / service",
        })
        return success

    # =========================================================================
    # GESTION DU PORTAIL & ACCÈS (Domolink-Portail)
    # =========================================================================

    def _get_gate_sensor_resolved_state(self, sensor_id: str | None, cfg: dict[str, Any]) -> tuple[str | None, bool]:
        """Résout l'état du capteur physique (entité unique ou étiquette)."""
        if not sensor_id:
            return None, False
        if sensor_id.startswith("label:"):
            entities = self.resolver.resolve_entities(TARGET_TYPE_LABEL, sensor_id[6:])
            if not entities:
                return None, False
            last_state = None
            for eid in entities:
                st = self.hass.states.get(eid)
                if st:
                    last_state = st.state
                    if self._is_gate_open_value(st.state, cfg):
                        return st.state, True
            return last_state, False
        else:
            st = self.hass.states.get(sensor_id)
            if st:
                return st.state, self._is_gate_open_value(st.state, cfg)
            return None, False

    def _resolve_switch_entities(self, target: str | None) -> list[str]:
        """Résout une cible de commande (entité unique ou étiquette)."""
        if not target:
            return []
        if target.startswith("label:"):
            return self.resolver.resolve_entities(TARGET_TYPE_LABEL, target[6:])
        return [target]

    def _init_gate_state_from_sensor(self, gate_id: str | None = None) -> None:
        """Détecte l'état initial d'un ou tous les portails/accès depuis Home Assistant."""
        gates = self.storage.get_gates()
        target_ids = [gate_id] if gate_id and gate_id in gates else list(gates.keys())
        for gid in target_ids:
            cfg = self.storage.get_gate_config(gid)
            st_mem = self._get_gate_internal_state(gid)
            sensor_id = cfg.get("sensor_entity")
            if sensor_id:
                raw_state, is_open = self._get_gate_sensor_resolved_state(sensor_id, cfg)
                if raw_state is not None:
                    st_mem["state"] = "open" if is_open else "closed"
                    if is_open:
                        now = dt_util.now()
                        st_mem["open_since"] = now.isoformat()
                        timer_min = self._get_current_timer_minutes(cfg, now)
                        if cfg.get("enabled", True) and not cfg.get("hold_open", False):
                            st_mem["target_close_time"] = (now + timedelta(minutes=timer_min)).isoformat()

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
        """Détermine le délai en minutes selon la plage Jour / Nuit (supporte le passage de minuit)."""
        current_time_str = now.strftime("%H:%M")
        day_start = cfg.get("day_start", "07:00")
        night_start = cfg.get("night_start", "22:00")
        if day_start <= night_start:
            is_day = day_start <= current_time_str < night_start
        else:
            is_day = current_time_str >= day_start or current_time_str < night_start
        if is_day:
            return int(cfg.get("timer_day_minutes", 10))
        return int(cfg.get("timer_night_minutes", 3))

    def get_gate_status(self, gate_id: str | None = None) -> dict[str, Any]:
        """Retourne l'état complet et temps réel d'un portail/accès pour le frontend."""
        gates = self.storage.get_gates()
        if not gate_id:
            gate_id = next(iter(gates)) if gates else "gate_1"
        cfg = self.storage.get_gate_config(gate_id)
        st_mem = self._get_gate_internal_state(gate_id)

        now = dt_util.now()
        travel_time = float(cfg.get("travel_time", 15))
        gate_type = cfg.get("gate_type", GATE_TYPE_SLIDING)

        # Calcul dynamique du mouvement progressif
        movement_start_iso = st_mem.get("movement_start")
        movement_elapsed = 0.0
        movement_progress = 0.0
        current_state = st_mem.get("state", "closed")

        if movement_start_iso and current_state in ("opening", "closing"):
            try:
                start_dt = datetime.fromisoformat(movement_start_iso)
                if start_dt.tzinfo is None:
                    start_dt = dt_util.as_local(start_dt)
                movement_elapsed = max(0.0, (now - start_dt).total_seconds())
                movement_progress = min(100.0, (movement_elapsed / max(1.0, travel_time)) * 100.0)
                if movement_elapsed >= travel_time:
                    if current_state == "opening":
                        st_mem["state"] = "open"
                        current_state = "open"
                        st_mem["movement_start"] = None
                    elif current_state == "closing":
                        sensor_id = cfg.get("sensor_entity")
                        is_open = False
                        if sensor_id:
                            _, is_open = self._get_gate_sensor_resolved_state(sensor_id, cfg)
                        if not is_open:
                            st_mem["state"] = "closed"
                            current_state = "closed"
                            st_mem["movement_start"] = None
            except Exception as err:
                _LOGGER.debug("Erreur calcul progression mouvement portail [%s]: %s", gate_id, err)

        # Calcul dynamique du compte à rebours en secondes
        countdown = 0
        target_iso = st_mem.get("target_close_time")
        if target_iso and current_state in ("open", "obstacle"):
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
            sensor_state, _ = self._get_gate_sensor_resolved_state(sensor_id, cfg)

        # Déterminer la période en cours (Jour ou Nuit)
        current_time_str = now.strftime("%H:%M")
        day_start = cfg.get("day_start", "07:00")
        night_start = cfg.get("night_start", "22:00")
        if day_start <= night_start:
            is_day = day_start <= current_time_str < night_start
        else:
            is_day = current_time_str >= day_start or current_time_str < night_start

        return {
            "id": gate_id,
            "name": cfg.get("name", "Portail Principal"),
            "config": cfg,
            "gate_type": gate_type,
            "travel_time": travel_time,
            "state": current_state,
            "is_open": current_state in ("open", "obstacle", "closing", "hold_open", "opening"),
            "movement_start": st_mem.get("movement_start"),
            "movement_elapsed": round(movement_elapsed, 1),
            "movement_progress": round(movement_progress, 1),
            "countdown_seconds": countdown,
            "target_close_time": target_iso,
            "open_since": st_mem.get("open_since"),
            "retries_done": st_mem.get("retries_done", 0),
            "max_retries": cfg.get("max_retries", 6),
            "last_action": st_mem.get("last_action", "Prêt"),
            "last_action_time": st_mem.get("last_action_time"),
            "hold_open": cfg.get("hold_open", False),
            "hold_open_until": cfg.get("hold_open_until"),
            "sensor_raw_state": sensor_state,
            "is_day": is_day,
            "current_timer_minutes": self._get_current_timer_minutes(cfg, now),
            "history": self.storage.get_gate_history(limit=20),
        }

    def get_all_gates_status(self) -> dict[str, dict[str, Any]]:
        """Retourne le statut complet de chaque accès configuré."""
        gates = self.storage.get_gates()
        return {gid: self.get_gate_status(gid) for gid in gates}

    async def _async_handle_gate_sensor_change(self, old_val: str, new_val: str, gate_id: str = "gate_1") -> None:
        """Gère un changement d'état du capteur physique pour un accès donné."""
        cfg = self.storage.get_gate_config(gate_id)
        st_mem = self._get_gate_internal_state(gate_id)
        is_now_open = self._is_gate_open_value(new_val, cfg)
        now = dt_util.now()
        travel_time = float(cfg.get("travel_time", 15))
        gate_name = cfg.get("name", gate_id)

        _LOGGER.info("DomoLink-Accès [%s]: Capteur '%s' -> '%s' (is_open=%s)", gate_name, old_val, new_val, is_now_open)

        if is_now_open:
            st_mem["open_since"] = now.isoformat()
            st_mem["movement_start"] = now.isoformat()
            st_mem["state"] = "opening"
            st_mem["last_action"] = "Ouverture en cours..."
            st_mem["last_action_time"] = now.isoformat()

            # Vérification Alerte Ouverture Nocturne / Intrusion
            current_time_str = now.strftime("%H:%M")
            day_start = cfg.get("day_start", "07:00")
            night_start = cfg.get("night_start", "22:00")
            if day_start <= night_start:
                is_day = day_start <= current_time_str < night_start
            else:
                is_day = current_time_str >= day_start or current_time_str < night_start

            if not is_day and cfg.get("night_intrusion_alert", False):
                alert_msg = f"🚨 [ALERTE NUIT] {gate_name} vient de s'ouvrir en plage nocturne ({current_time_str}) !"
                _LOGGER.warning("DomoLink-Accès: %s", alert_msg)
                await self._async_send_gate_notification(alert_msg, gate_id=gate_id)
                try:
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": f"🚨 Alerte Ouverture Nocturne : {gate_name}",
                            "message": alert_msg,
                            "notification_id": f"domolink_night_alert_{gate_id}",
                        },
                        blocking=False,
                    )
                except Exception:
                    pass

                light_ent = cfg.get("night_intrusion_light_entity")
                if light_ent:
                    try:
                        for target_light in self._resolve_switch_entities(light_ent):
                            dom = target_light.split(".")[0]
                            await self.hass.services.async_call(
                                dom, "turn_on", {"entity_id": target_light}, blocking=False
                            )
                    except Exception as err:
                        _LOGGER.error("DomoLink-Accès: Erreur allumage éclairage nocturne %s: %s", light_ent, err)

                await self.storage.async_add_gate_history({
                    "timestamp": now.isoformat(),
                    "gate_id": gate_id,
                    "event": "ALERTE_NUIT",
                    "status": "INTRUSION_ALERT",
                    "details": alert_msg,
                })

            # Tâche asynchrone pour marquer la fin de la manœuvre d'ouverture
            async def _async_complete_opening_maneuver():
                await asyncio.sleep(travel_time)
                if st_mem.get("state") == "opening":
                    now_end = dt_util.now()
                    st_mem["movement_start"] = None
                    if cfg.get("hold_open", False):
                        st_mem["state"] = "hold_open"
                        st_mem["target_close_time"] = None
                    elif cfg.get("enabled", True):
                        timer_min = self._get_current_timer_minutes(cfg, now_end)
                        target = now_end + timedelta(minutes=timer_min)
                        st_mem["state"] = "open"
                        st_mem["target_close_time"] = target.isoformat()
                        st_mem["retries_done"] = 0
                    else:
                        st_mem["state"] = "open"
                    st_mem["last_action"] = "Ouverture terminée"
                    st_mem["last_action_time"] = now_end.isoformat()
                    self.data["gate"] = self.get_gate_status()
                    self.data["gates"] = self.get_all_gates_status()
                    self.async_set_updated_data(self.data)

            if gate_id in self._gate_opening_tasks and not self._gate_opening_tasks[gate_id].done():
                self._gate_opening_tasks[gate_id].cancel()
            self._gate_opening_tasks[gate_id] = self.hass.async_create_task(_async_complete_opening_maneuver())

            if cfg.get("hold_open", False):
                await self.storage.async_add_gate_history({
                    "timestamp": now.isoformat(),
                    "gate_id": gate_id,
                    "event": "OUVERTURE",
                    "status": "HOLD_OPEN",
                    "details": f"[{gate_name}] Ouvert (mode maintien activé, fermeture auto suspendue)",
                })
            elif cfg.get("enabled", True):
                timer_min = self._get_current_timer_minutes(cfg, now)
                await self.storage.async_add_gate_history({
                    "timestamp": now.isoformat(),
                    "gate_id": gate_id,
                    "event": "OUVERTURE",
                    "status": "TIMER_STARTED",
                    "details": f"[{gate_name}] En ouverture (fermeture automatique programmée dans {timer_min} min)",
                })
        else:
            # L'accès est fermé
            st_mem["state"] = "closed"
            st_mem["movement_start"] = None
            st_mem["target_close_time"] = None
            st_mem["retries_done"] = 0
            st_mem["open_since"] = None
            st_mem["last_action"] = "Fermeture confirmée"
            st_mem["last_action_time"] = now.isoformat()
            await self.storage.async_add_gate_history({
                "timestamp": now.isoformat(),
                "gate_id": gate_id,
                "event": "FERMETURE",
                "status": "CLOSED",
                "details": f"[{gate_name}] Fermé et sécurisé",
            })

        self.data["gate"] = self.get_gate_status()
        self.data["gates"] = self.get_all_gates_status()
        self.async_set_updated_data(self.data)

    async def _async_gate_tick(self, now: datetime) -> None:
        """Vérification rapide (toutes les 5s) pour le décompte et l'auto-fermeture de tous les accès."""
        now_local = dt_util.as_local(now)
        gates = self.storage.get_gates()

        for gid, cfg in gates.items():
            st_mem = self._get_gate_internal_state(gid)

            # 1. Vérifier l'expiration du maintien ouvert temporisé
            hold_until_str = cfg.get("hold_open_until")
            if hold_until_str:
                try:
                    hold_until_dt = datetime.fromisoformat(hold_until_str)
                    if hold_until_dt.tzinfo is None:
                        hold_until_dt = dt_util.as_local(hold_until_dt)
                    if now_local >= hold_until_dt:
                        _LOGGER.info("DomoLink-Accès [%s]: Expiration du maintien ouvert temporisé", gid)
                        await self.async_gate_set_hold_open(False, gate_id=gid)
                except Exception as err:
                    _LOGGER.debug("Erreur parsing hold_open_until [%s]: %s", gid, err)

            # 2. Vérifier si l'échéance de fermeture automatique est arrivée
            target_iso = st_mem.get("target_close_time")
            if (
                target_iso
                and cfg.get("enabled", True)
                and not cfg.get("hold_open", False)
                and not st_mem.get("check_in_progress", False)
                and st_mem.get("state") in ("open", "obstacle")
            ):
                try:
                    target_dt = datetime.fromisoformat(target_iso)
                    if target_dt.tzinfo is None:
                        target_dt = dt_util.as_local(target_dt)
                    if now_local >= target_dt:
                        st_mem["target_close_time"] = None
                        if gid in self._gate_tasks and not self._gate_tasks[gid].done():
                            self._gate_tasks[gid].cancel()
                        self._gate_tasks[gid] = self.hass.async_create_task(self.async_gate_close_cycle(gate_id=gid))
                except Exception as err:
                    _LOGGER.error("DomoLink-Accès [%s]: Erreur tick fermeture auto: %s", gid, err)

        # 3. Rafraîchir l'état pour le frontend
        self.data["gate"] = self.get_gate_status()
        self.data["gates"] = self.get_all_gates_status()
        self.async_set_updated_data(self.data)

    async def async_gate_close_cycle(self, gate_id: str | None = None) -> None:
        """Exécute le cycle complet : notification préalable, impulsion, vérification et réessais."""
        gates = self.storage.get_gates()
        if not gate_id:
            gate_id = next(iter(gates)) if gates else "gate_1"
        cfg = self.storage.get_gate_config(gate_id)
        st_mem = self._get_gate_internal_state(gate_id)
        gate_name = cfg.get("name", "Portail")

        max_retries = int(cfg.get("max_retries", 6))
        check_delay = int(cfg.get("check_delay", 60))
        retry_interval = int(cfg.get("retry_interval_minutes", 10))

        st_mem["check_in_progress"] = True
        st_mem["state"] = "closing"
        now = dt_util.now()
        st_mem["movement_start"] = now.isoformat()
        current_retry = st_mem.get("retries_done", 0) + 1

        _LOGGER.info("DomoLink-Accès [%s]: Démarrage cycle fermeture (Essai %d/%d)", gate_name, current_retry, max_retries)

        # 1. Envoi SMS / notification d'avertissement
        await self._async_send_gate_notification(
            f"[{gate_name}] Resté ouvert. Lancement de la fermeture automatique (Tentative {current_retry}/{max_retries}).",
            gate_id=gate_id,
        )

        # 2. Actionner la commande de fermeture selon le type
        await self.async_gate_trigger_action(mode="close", gate_id=gate_id)

        st_mem["last_action"] = f"Action de fermeture envoyée (Tentative {current_retry}/{max_retries})"
        st_mem["last_action_time"] = now.isoformat()
        self.data["gate"] = self.get_gate_status()
        self.data["gates"] = self.get_all_gates_status()
        self.async_set_updated_data(self.data)

        # 3. Attente du temps de manœuvre (ex: 60 secondes)
        await asyncio.sleep(check_delay)

        # 4. Vérification de l'état réel du capteur
        sensor_id = cfg.get("sensor_entity")
        is_still_open = True
        if sensor_id:
            _, is_still_open = self._get_gate_sensor_resolved_state(sensor_id, cfg)

        now_after = dt_util.now()

        if not is_still_open:
            # Succès : Bien fermé
            st_mem["state"] = "closed"
            st_mem["retries_done"] = 0
            st_mem["check_in_progress"] = False
            st_mem["target_close_time"] = None
            st_mem["last_action"] = "Fermeture réussie confirmée"
            st_mem["last_action_time"] = now_after.isoformat()

            await self._async_send_gate_notification(f"[{gate_name}] Maintenant bien fermé et sécurisé.", gate_id=gate_id)
            await self.storage.async_add_gate_history({
                "timestamp": now_after.isoformat(),
                "gate_id": gate_id,
                "event": "FERMETURE_AUTO",
                "status": "SUCCESS",
                "details": f"[{gate_name}] Fermeture automatique réussie à la tentative {current_retry}/{max_retries}",
            })
        else:
            # Échec : Toujours ouvert (obstacle / blocage)
            st_mem["retries_done"] = current_retry
            st_mem["check_in_progress"] = False

            if current_retry < max_retries:
                st_mem["state"] = "obstacle"
                st_mem["target_close_time"] = (now_after + timedelta(minutes=retry_interval)).isoformat()
                st_mem["last_action"] = f"Obstacle détecté (Essai {current_retry}/{max_retries})"
                st_mem["last_action_time"] = now_after.isoformat()

                await self._async_send_gate_notification(
                    f"[Alerte {gate_name}] Échec de fermeture (obstacle détecté). Prochaine tentative dans {retry_interval} min (essai {current_retry}/{max_retries}).",
                    gate_id=gate_id,
                )
                await self.storage.async_add_gate_history({
                    "timestamp": now_after.isoformat(),
                    "gate_id": gate_id,
                    "event": "OBSTACLE",
                    "status": "RETRY_SCHEDULED",
                    "details": f"[{gate_name}] Obstacle détecté, réessai {current_retry + 1}/{max_retries} dans {retry_interval} min",
                })
            else:
                st_mem["state"] = "obstacle"
                st_mem["target_close_time"] = None
                st_mem["last_action"] = f"URGENT: Échec après {max_retries} tentatives"
                st_mem["last_action_time"] = now_after.isoformat()

                await self._async_send_gate_notification(
                    f"[URGENT] {gate_name} est toujours OUVERT après {max_retries} tentatives. Intervention manuelle requise !",
                    gate_id=gate_id,
                )
                await self.storage.async_add_gate_history({
                    "timestamp": now_after.isoformat(),
                    "gate_id": gate_id,
                    "event": "ECHEC_CRITIQUE",
                    "status": "FAILED",
                    "details": f"[{gate_name}] Arrêt d'urgence des fermetures automatiques après {max_retries} tentatives",
                })

        self.data["gate"] = self.get_gate_status()
        self.data["gates"] = self.get_all_gates_status()
        self.async_set_updated_data(self.data)

    async def async_gate_trigger_action(self, mode: str = "toggle", gate_id: str | None = None) -> bool:
        """Déclenche la commande matérielle d'un accès selon le type d'interrupteur configuré."""
        gates = self.storage.get_gates()
        if not gate_id:
            gate_id = next(iter(gates)) if gates else "gate_1"
        cfg = self.storage.get_gate_config(gate_id)
        st_mem = self._get_gate_internal_state(gate_id)
        gate_name = cfg.get("name", "Accès")

        switch_type = cfg.get("switch_type", GATE_SWITCH_TYPE_PULSE)
        switch_entity = cfg.get("switch_entity")
        close_switch_entity = cfg.get("close_switch_entity")
        pedestrian_switch_entity = cfg.get("pedestrian_switch_entity")
        pulse_duration = float(cfg.get("pulse_duration", 1.0))

        # Commande dédiée à l'accès piéton / livreur (avec switch dédié OU cycle partiel sur switch principal)
        if mode == "pedestrian":
            ped_close_min = float(cfg.get("pedestrian_close_minutes", 2))
            if pedestrian_switch_entity:
                try:
                    targets = self._resolve_switch_entities(pedestrian_switch_entity)
                    for ent in targets:
                        domain = ent.split(".")[0]
                        await self.hass.services.async_call(domain, "turn_on", {"entity_id": ent}, blocking=True)
                    if pulse_duration > 0:
                        await asyncio.sleep(pulse_duration)
                        for ent in targets:
                            domain = ent.split(".")[0]
                            st = self.hass.states.get(ent)
                            if st and st.state == "on":
                                await self.hass.services.async_call(domain, "turn_off", {"entity_id": ent}, blocking=True)

                    now = dt_util.now()
                    st_mem["state"] = "opening"
                    st_mem["movement_start"] = now.isoformat()
                    st_mem["last_action"] = "Ouverture piéton en cours..."
                    st_mem["last_action_time"] = now.isoformat()
                    if ped_close_min > 0 and cfg.get("enabled", True):
                        st_mem["target_close_time"] = (now + timedelta(minutes=ped_close_min)).isoformat()
                    self.data["gate"] = self.get_gate_status()
                    self.data["gates"] = self.get_all_gates_status()
                    self.async_set_updated_data(self.data)
                    await self.storage.async_add_gate_history({
                        "timestamp": now.isoformat(),
                        "gate_id": gate_id,
                        "event": "OUVERTURE_PIETON",
                        "status": "PEDESTRIAN",
                        "details": f"[{gate_name}] Commande d'accès piéton dédiée déclenchée",
                    })
                    return True
                except Exception as err:
                    _LOGGER.error("DomoLink-Accès [%s]: Erreur commande accès piéton: %s", gate_name, err)
                    return False
            elif switch_entity and switch_type in (GATE_SWITCH_TYPE_PULSE, GATE_SWITCH_TYPE_COVER):
                # Cycle intelligent d'ouverture partielle (Impulsion Ouverture -> Attente X sec -> Impulsion Stop)
                ped_open_sec = max(2.0, float(cfg.get("pedestrian_open_seconds", 5)))
                try:
                    targets = self._resolve_switch_entities(switch_entity)
                    if switch_type == GATE_SWITCH_TYPE_COVER:
                        for ent in targets:
                            await self.hass.services.async_call("cover", "open_cover", {"entity_id": ent}, blocking=True)
                    else:
                        for ent in targets:
                            domain = ent.split(".")[0]
                            await self.hass.services.async_call(domain, "turn_on", {"entity_id": ent}, blocking=True)
                        if pulse_duration > 0:
                            await asyncio.sleep(pulse_duration)
                            for ent in targets:
                                domain = ent.split(".")[0]
                                st = self.hass.states.get(ent)
                                if st and st.state == "on":
                                    await self.hass.services.async_call(domain, "turn_off", {"entity_id": ent}, blocking=True)

                    now = dt_util.now()
                    st_mem["state"] = "opening"
                    st_mem["movement_start"] = now.isoformat()
                    st_mem["last_action"] = f"Ouverture Piéton/Livreur ({int(ped_open_sec)}s)..."
                    st_mem["last_action_time"] = now.isoformat()
                    self.data["gate"] = self.get_gate_status()
                    self.data["gates"] = self.get_all_gates_status()
                    self.async_set_updated_data(self.data)

                    async def _async_stop_pedestrian_opening():
                        await asyncio.sleep(ped_open_sec)
                        # Envoyer la seconde impulsion pour stopper l'ouverture à mi-course
                        if switch_type == GATE_SWITCH_TYPE_COVER:
                            for ent in targets:
                                await self.hass.services.async_call("cover", "stop_cover", {"entity_id": ent}, blocking=True)
                        else:
                            for ent in targets:
                                domain = ent.split(".")[0]
                                await self.hass.services.async_call(domain, "turn_on", {"entity_id": ent}, blocking=True)
                            if pulse_duration > 0:
                                await asyncio.sleep(pulse_duration)
                                for ent in targets:
                                    domain = ent.split(".")[0]
                                    st = self.hass.states.get(ent)
                                    if st and st.state == "on":
                                        await self.hass.services.async_call(domain, "turn_off", {"entity_id": ent}, blocking=True)
                        now_stop = dt_util.now()
                        st_mem["state"] = "open"
                        st_mem["movement_start"] = None
                        if ped_close_min > 0:
                            st_mem["target_close_time"] = (now_stop + timedelta(minutes=ped_close_min)).isoformat()
                            st_mem["last_action"] = f"Ouvert en mode Piéton (fermeture dans {int(ped_close_min)} min)"
                        else:
                            st_mem["last_action"] = "Ouvert partiellement (Mode Piéton)"
                        st_mem["last_action_time"] = now_stop.isoformat()
                        self.data["gate"] = self.get_gate_status()
                        self.data["gates"] = self.get_all_gates_status()
                        self.async_set_updated_data(self.data)

                    if gate_id in self._gate_opening_tasks and not self._gate_opening_tasks[gate_id].done():
                        self._gate_opening_tasks[gate_id].cancel()
                    self._gate_opening_tasks[gate_id] = self.hass.async_create_task(_async_stop_pedestrian_opening())

                    await self.storage.async_add_gate_history({
                        "timestamp": now.isoformat(),
                        "gate_id": gate_id,
                        "event": "OUVERTURE_PIETON",
                        "status": "PEDESTRIAN",
                        "details": f"[{gate_name}] Ouverture partielle Piéton/Livreur ({int(ped_open_sec)}s, refermeture dans {int(ped_close_min)} min)",
                    })
                    return True
                except Exception as err:
                    _LOGGER.error("DomoLink-Accès [%s]: Erreur cycle ouverture partielle piéton: %s", gate_name, err)
                    return False
            else:
                _LOGGER.warning("DomoLink-Accès [%s]: Aucun switch configuré pour l'accès piéton", gate_name)
                return False

        if not switch_entity:
            _LOGGER.warning("DomoLink-Accès [%s]: Aucun switch configuré pour commander l'accès", gate_name)
            return False

        # Protection directionnelle intelligente sur contact sec impulsionnel :
        # Ne pas envoyer d'impulsion d'ouverture si déjà ouvert, ni de fermeture si déjà fermé
        current_st = st_mem.get("state", "closed")
        if switch_type == GATE_SWITCH_TYPE_PULSE:
            if mode == "open" and current_st in ("open", "opening", "hold_open"):
                _LOGGER.info("DomoLink-Accès [%s]: Déjà ouvert (%s), impulsion d'ouverture ignorée", gate_name, current_st)
                return True
            if mode == "close" and current_st == "closed":
                sensor_id = cfg.get("sensor_entity")
                is_phys_open = False
                if sensor_id:
                    _, is_phys_open = self._get_gate_sensor_resolved_state(sensor_id, cfg)
                if not is_phys_open:
                    _LOGGER.info("DomoLink-Accès [%s]: Déjà fermé, impulsion de fermeture ignorée", gate_name)
                    return True

        try:
            if switch_type == GATE_SWITCH_TYPE_PULSE:
                targets = self._resolve_switch_entities(switch_entity)
                for ent in targets:
                    domain = ent.split(".")[0]
                    await self.hass.services.async_call(domain, "turn_on", {"entity_id": ent}, blocking=True)
                if pulse_duration > 0:
                    await asyncio.sleep(pulse_duration)
                    for ent in targets:
                        domain = ent.split(".")[0]
                        st = self.hass.states.get(ent)
                        if st and st.state == "on":
                            await self.hass.services.async_call(domain, "turn_off", {"entity_id": ent}, blocking=True)

            elif switch_type == GATE_SWITCH_TYPE_DUAL:
                target_setting = close_switch_entity if mode == "close" and close_switch_entity else switch_entity
                targets = self._resolve_switch_entities(target_setting)
                for ent in targets:
                    domain = ent.split(".")[0]
                    await self.hass.services.async_call(domain, "turn_on", {"entity_id": ent}, blocking=True)
                if pulse_duration > 0:
                    await asyncio.sleep(pulse_duration)
                    for ent in targets:
                        domain = ent.split(".")[0]
                        st = self.hass.states.get(ent)
                        if st and st.state == "on":
                            await self.hass.services.async_call(domain, "turn_off", {"entity_id": ent}, blocking=True)

            elif switch_type == GATE_SWITCH_TYPE_COVER:
                targets = self._resolve_switch_entities(switch_entity)
                for ent in targets:
                    if mode == "close":
                        await self.hass.services.async_call("cover", "close_cover", {"entity_id": ent}, blocking=True)
                    elif mode == "open":
                        await self.hass.services.async_call("cover", "open_cover", {"entity_id": ent}, blocking=True)
                    else:
                        await self.hass.services.async_call("cover", "toggle", {"entity_id": ent}, blocking=True)

            elif switch_type == GATE_SWITCH_TYPE_TOGGLE:
                targets = self._resolve_switch_entities(switch_entity)
                action = "turn_off" if mode == "close" else "turn_on"
                for ent in targets:
                    domain = ent.split(".")[0]
                    await self.hass.services.async_call(domain, action, {"entity_id": ent}, blocking=True)

            now = dt_util.now()
            current_st = st_mem.get("state", "closed")
            if mode == "close" or (mode == "toggle" and current_st in ("open", "obstacle", "hold_open")):
                st_mem["state"] = "closing"
                st_mem["movement_start"] = now.isoformat()
                st_mem["last_action"] = "Fermeture en cours..."
            else:
                st_mem["state"] = "opening"
                st_mem["movement_start"] = now.isoformat()
                st_mem["last_action"] = "Ouverture en cours..."
            st_mem["last_action_time"] = now.isoformat()
            self.data["gate"] = self.get_gate_status()
            self.data["gates"] = self.get_all_gates_status()
            self.async_set_updated_data(self.data)

            return True
        except Exception as err:
            _LOGGER.error("DomoLink-Accès [%s]: Erreur commande (%s): %s", gate_name, switch_type, err)
            return False

    async def async_gate_set_hold_open(self, enabled: bool, duration_minutes: int | None = None, gate_id: str | None = None) -> None:
        """Active ou désactive le mode maintien ouvert (permanent ou temporisé) pour un accès."""
        gates = self.storage.get_gates()
        if not gate_id:
            gate_id = next(iter(gates)) if gates else "gate_1"
        cfg = self.storage.get_gate_config(gate_id)
        st_mem = self._get_gate_internal_state(gate_id)
        gate_name = cfg.get("name", "Accès")
        now = dt_util.now()

        hold_until_iso = None
        if enabled and duration_minutes and duration_minutes > 0:
            hold_until_iso = (now + timedelta(minutes=duration_minutes)).isoformat()

        cfg["hold_open"] = enabled
        cfg["hold_open_until"] = hold_until_iso
        await self.storage.async_save_gate(gate_id, cfg)

        if enabled:
            st_mem["target_close_time"] = None
            if st_mem.get("state") == "open":
                st_mem["state"] = "hold_open"
            desc = f"Maintien ouvert activé ({duration_minutes} min)" if duration_minutes else "Maintien ouvert permanent activé"
        else:
            desc = "Maintien ouvert désactivé"
            sensor_id = cfg.get("sensor_entity")
            if sensor_id:
                _, is_open = self._get_gate_sensor_resolved_state(sensor_id, cfg)
                if is_open:
                    timer_min = self._get_current_timer_minutes(cfg, now)
                    st_mem["state"] = "open"
                    st_mem["target_close_time"] = (now + timedelta(minutes=timer_min)).isoformat()

        await self.storage.async_add_gate_history({
            "timestamp": now.isoformat(),
            "gate_id": gate_id,
            "event": "MAINTIEN_OUVERT",
            "status": "ON" if enabled else "OFF",
            "details": f"[{gate_name}] {desc}",
        })

        self.data["gate"] = self.get_gate_status()
        self.data["gates"] = self.get_all_gates_status()
        self.async_set_updated_data(self.data)

    async def _async_send_gate_notification(self, message: str, gate_id: str | None = None) -> None:
        """Envoie une notification via le service configuré pour cet accès."""
        cfg = self.storage.get_gate_config(gate_id)
        notify_service = cfg.get("notify_service")
        if not notify_service:
            return

        _LOGGER.info("DomoLink-Accès [%s]: Envoi notification -> %s : %s", cfg.get("name", gate_id), notify_service, message)
        try:
            if notify_service.startswith("notify."):
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"entity_id": notify_service, "message": message},
                    blocking=True,
                )
            else:
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
                _LOGGER.error("DomoLink-Accès: Échec d'envoi notification (%s): %s", notify_service, fallback_err)

