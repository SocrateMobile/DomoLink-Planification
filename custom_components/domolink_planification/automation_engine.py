"""Moteur d'automatisations modernes et performantes pour DomoLink-Planification.

Gère les déclencheurs (événements, boutons Zigbee/ZHA/Z2M/Shelly, états, seuils, soleil, calendrier),
les filtres/conditions contextuelles, l'anti-rebond matériel, les modes d'exécution,
le contrôle natif des accès DomoLink (Portails, Portes, Garages),
ainsi que la traçabilité complète de chaque étape d'exécution.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time
import fnmatch
import logging
import time as time_module
from typing import Any, Callable

from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    AUTO_ACTION_DELAY,
    AUTO_ACTION_DEVICE,
    AUTO_ACTION_GATE,
    AUTO_ACTION_IF_THEN,
    AUTO_ACTION_NOTIFICATION,
    AUTO_ACTION_SERVICE,
    AUTO_COND_ALARM,
    AUTO_COND_AND,
    AUTO_COND_HOLIDAY,
    AUTO_COND_NOT,
    AUTO_COND_NUMERIC_STATE,
    AUTO_COND_OR,
    AUTO_COND_PRESENCE,
    AUTO_COND_STATE,
    AUTO_COND_SUN,
    AUTO_COND_TIME_WINDOW,
    AUTO_TRIGGER_BUTTON,
    AUTO_TRIGGER_EVENT,
    AUTO_TRIGGER_NUMERIC_STATE,
    AUTO_TRIGGER_SOLAR,
    AUTO_TRIGGER_STATE,
    AUTO_TRIGGER_TIME,
    AUTO_TRIGGER_ZONE,
    COUNTRY_FR,
    EXEC_MODE_PARALLEL,
    EXEC_MODE_QUEUED,
    EXEC_MODE_RESTART,
    EXEC_MODE_SINGLE,
    HOLIDAY_MODE_ALWAYS,
    HOLIDAY_MODE_EXCLUDE,
    HOLIDAY_MODE_ONLY,
    HOLIDAY_MODE_WEEKEND,
    TARGET_TYPE_GATE,
)
from .holidays import HolidayEngine
from .storage import PlanificationStorage
from .target_resolver import TargetResolver

_LOGGER = logging.getLogger(__name__)


class AutomationEngine:
    """Moteur central d'automatisations pour DomoLink-Planification."""

    def __init__(
        self,
        hass: HomeAssistant,
        storage: PlanificationStorage,
        resolver: TargetResolver,
        coordinator: Any = None,
    ) -> None:
        self.hass = hass
        self.storage = storage
        self.resolver = resolver
        self.coordinator = coordinator

        self._unsub_listeners: list[Callable[[], None]] = []
        self._running_tasks: dict[str, list[asyncio.Task]] = {}
        self._last_triggered_timestamps: dict[str, float] = {}

        # Mode Sniffer / Apprentissage de bouton en direct
        self._sniffer_active: bool = False
        self._sniffer_until: float = 0.0
        self._sniffed_event: dict[str, Any] | None = None

    async def async_start(self) -> None:
        """Démarre le moteur d'automatisations et abonne les écouteurs."""
        self.async_stop()
        self._setup_event_listeners()
        _LOGGER.info("DomoLink-Planification: Moteur d'automatisations initialisé et actif.")

    def async_stop(self) -> None:
        """Arrête tous les écouteurs et annule les tâches en cours."""
        for unsub in self._unsub_listeners:
            try:
                unsub()
            except Exception:
                pass
        self._unsub_listeners.clear()

        # Annuler les tâches en cours
        for task_list in self._running_tasks.values():
            for t in task_list:
                if not t.done():
                    t.cancel()
        self._running_tasks.clear()

    def _setup_event_listeners(self) -> None:
        """Abonne les écouteurs d'événements HA nécessaires."""
        # 1. Écouteur pour zha_event (boutons Xiaomi, Aqara, Sonoff, IKEA, etc.)
        @callback
        def _async_on_zha_event(event: Event) -> None:
            self._handle_incoming_event("zha_event", event.data)

        # 2. Écouteur pour deconz_event
        @callback
        def _async_on_deconz_event(event: Event) -> None:
            self._handle_incoming_event("deconz_event", event.data)

        # 3. Écouteur pour shelly.click
        @callback
        def _async_on_shelly_event(event: Event) -> None:
            self._handle_incoming_event("shelly.click", event.data)

        # 4. Écouteur de changement d'état (capteurs, interrupteurs, trackers, Z2M sensor.*_action)
        @callback
        def _async_on_state_changed(event: Event) -> None:
            self._handle_state_changed_event(event.data)

        try:
            self._unsub_listeners.append(
                self.hass.bus.async_listen("zha_event", _async_on_zha_event)
            )
            self._unsub_listeners.append(
                self.hass.bus.async_listen("deconz_event", _async_on_deconz_event)
            )
            self._unsub_listeners.append(
                self.hass.bus.async_listen("shelly.click", _async_on_shelly_event)
            )
            self._unsub_listeners.append(
                self.hass.bus.async_listen(EVENT_STATE_CHANGED, _async_on_state_changed)
            )
        except Exception as err:
            _LOGGER.error("Erreur lors de l'enregistrement des écouteurs d'automatisations: %s", err)

    # -------------------------------------------------------------------------
    # Mode Sniffer (Écouter & Apprendre un bouton en direct)
    # -------------------------------------------------------------------------
    def start_sniffer(self, duration_seconds: int = 30) -> None:
        """Active le mode sniffer pour capturer le prochain appui sur un bouton physique."""
        self._sniffer_active = True
        self._sniffer_until = time_module.time() + duration_seconds
        self._sniffed_event = None
        _LOGGER.info("DomoLink: Sniffer actif pour %d secondes...", duration_seconds)

    def get_sniffed_event(self) -> dict[str, Any] | None:
        """Retourne l'événement capturé par le sniffer."""
        if self._sniffer_active and time_module.time() > self._sniffer_until:
            self._sniffer_active = False

        return {
            "active": self._sniffer_active,
            "remaining_seconds": max(0, int(self._sniffer_until - time_module.time())) if self._sniffer_active else 0,
            "event": self._sniffed_event,
        }

    def _check_sniffer(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Si le sniffer est actif, capture l'événement."""
        if not self._sniffer_active:
            return

        if time_module.time() > self._sniffer_until:
            self._sniffer_active = False
            return

        # Filtrer les événements pertinents (boutons, télécommandes, clics)
        if (
            event_type in ("zha_event", "deconz_event", "shelly.click")
            or "click" in str(event_data).lower()
            or "button" in str(event_data).lower()
        ):
            self._sniffed_event = {
                "event_type": event_type,
                "event_data": dict(event_data),
                "timestamp": dt_util.now().isoformat(),
            }
            self._sniffer_active = False
            _LOGGER.info("DomoLink Sniffer: Événement capturé avec succès: %s", event_type)

    # -------------------------------------------------------------------------
    # Réception et acheminement des événements
    # -------------------------------------------------------------------------
    def _handle_incoming_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Traite un événement de bus (zha_event, deconz, shelly.click, etc.)."""
        self._check_sniffer(event_type, event_data)

        automations = self.storage.get_automations()
        for auto_id, auto in automations.items():
            if not auto.get("enabled", True):
                continue

            triggers = auto.get("triggers", [])
            for trigger in triggers:
                t_type = trigger.get("type", AUTO_TRIGGER_EVENT)

                # 1. Déclencheur Événement générique
                if t_type == AUTO_TRIGGER_EVENT:
                    if trigger.get("event_type") == event_type:
                        filter_data = trigger.get("event_data", {})
                        if self._match_dict_subset(filter_data, event_data):
                            self._trigger_automation(auto_id, auto, {
                                "trigger_type": AUTO_TRIGGER_EVENT,
                                "event_type": event_type,
                                "event_data": event_data,
                            })
                            break

                # 2. Déclencheur Bouton Universel (Spécialisé Zigbee/ZHA/Z2M/Shelly)
                elif t_type == AUTO_TRIGGER_BUTTON:
                    if self._match_button_trigger(trigger, event_type, event_data):
                        self._trigger_automation(auto_id, auto, {
                            "trigger_type": AUTO_TRIGGER_BUTTON,
                            "event_type": event_type,
                            "event_data": event_data,
                        })
                        break

    def _handle_state_changed_event(self, event_data: dict[str, Any]) -> None:
        """Traite les changements d'état d'entités HA."""
        entity_id = event_data.get("entity_id")
        old_state = event_data.get("old_state")
        new_state = event_data.get("new_state")

        if not entity_id or not new_state:
            return

        old_val = old_state.state if old_state else None
        new_val = new_state.state

        if old_val == new_val:
            return

        # Support Sniffer pour Zigbee2MQTT (sensor.*_action)
        if self._sniffer_active and entity_id.endswith("_action") and new_val not in ("", STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._sniffed_event = {
                "event_type": "z2m_action",
                "event_data": {
                    "entity_id": entity_id,
                    "device_id": entity_id,
                    "command": new_val,
                },
                "timestamp": dt_util.now().isoformat(),
            }
            self._sniffer_active = False

        automations = self.storage.get_automations()
        for auto_id, auto in automations.items():
            if not auto.get("enabled", True):
                continue

            for trigger in auto.get("triggers", []):
                t_type = trigger.get("type")

                # Déclencheur Bouton Universel via entité Zigbee2MQTT (sensor.*_action)
                if t_type == AUTO_TRIGGER_BUTTON:
                    trig_ent = trigger.get("entity_id") or trigger.get("device_id")
                    if trig_ent == entity_id and new_val not in ("", STATE_UNKNOWN, STATE_UNAVAILABLE):
                        synthetic_data = {"device_id": entity_id, "command": new_val}
                        if self._match_button_trigger(trigger, "state_changed", synthetic_data):
                            self._trigger_automation(auto_id, auto, {
                                "trigger_type": AUTO_TRIGGER_BUTTON,
                                "entity_id": entity_id,
                                "action": new_val,
                            })
                            break

                # Déclencheur État standard
                elif t_type == AUTO_TRIGGER_STATE:
                    if trigger.get("entity_id") == entity_id:
                        to_filter = trigger.get("to")
                        from_filter = trigger.get("from")

                        to_match = (not to_filter) or (str(to_filter).lower() == str(new_val).lower())
                        from_match = (not from_filter) or (old_val is not None and str(from_filter).lower() == str(old_val).lower())

                        if to_match and from_match:
                            self._trigger_automation(auto_id, auto, {
                                "trigger_type": AUTO_TRIGGER_STATE,
                                "entity_id": entity_id,
                                "from_state": old_val,
                                "to_state": new_val,
                            })
                            break

                # Déclencheur Seuil Numérique (Numeric State)
                elif t_type == AUTO_TRIGGER_NUMERIC_STATE:
                    if trigger.get("entity_id") == entity_id:
                        try:
                            new_num = float(new_val)
                            old_num = float(old_val) if old_val is not None else None
                            above = trigger.get("above")
                            below = trigger.get("below")

                            crossed = False
                            if above is not None and str(above) != "":
                                above_val = float(above)
                                if new_num > above_val and (old_num is None or old_num <= above_val):
                                    crossed = True

                            if below is not None and str(below) != "":
                                below_val = float(below)
                                if new_num < below_val and (old_num is None or old_num >= below_val):
                                    crossed = True

                            if crossed:
                                self._trigger_automation(auto_id, auto, {
                                    "trigger_type": AUTO_TRIGGER_NUMERIC_STATE,
                                    "entity_id": entity_id,
                                    "value": new_num,
                                })
                                break
                        except (ValueError, TypeError):
                            pass

    # -------------------------------------------------------------------------
    # Filtres & Pattern Matching Déclencheurs
    # -------------------------------------------------------------------------
    @staticmethod
    def _match_dict_subset(pattern: dict[str, Any], target: dict[str, Any]) -> bool:
        """Vérifie récursivement si target contient tous les critères de pattern."""
        if not pattern:
            return True
        for k, v in pattern.items():
            if k not in target:
                return False
            target_val = target[k]
            if isinstance(v, dict):
                if not isinstance(target_val, dict) or not AutomationEngine._match_dict_subset(v, target_val):
                    return False
            elif isinstance(v, str) and "*" in v:
                if not fnmatch.fnmatch(str(target_val), v):
                    return False
            else:
                if str(v).lower() != str(target_val).lower():
                    return False
        return True

    @staticmethod
    def _match_button_trigger(trigger: dict[str, Any], event_type: str, event_data: dict[str, Any]) -> bool:
        """Vérifie si un événement correspond à un appui de bouton configuré."""
        # 1. Vérifier le Device ID ou IEEE
        target_device = trigger.get("device_id")
        if target_device:
            event_device = (
                event_data.get("device_id")
                or event_data.get("device_ieee")
                or event_data.get("id")
                or event_data.get("entity_id")
            )
            if not event_device or str(target_device).lower() != str(event_device).lower():
                return False

        # 2. Vérifier l'action demandée (single, double, hold/long, release, any)
        desired_action = trigger.get("action", "single")
        if desired_action == "any":
            return True

        # Extraire la commande et les arguments (ZHA, deCONZ, Shelly, Z2M)
        command = str(event_data.get("command") or event_data.get("click_type") or event_data.get("event") or "").lower()
        args = event_data.get("args", {})
        click_type = ""

        if isinstance(args, dict):
            click_type = str(args.get("click_type") or args.get("press_type") or "").lower()
        elif isinstance(args, list) and args:
            click_type = str(args[0]).lower()

        # Dictionnaire des équivalences pour boutons Xiaomi, Aqara, Sonoff, Philips, IKEA, Shelly
        single_clicks = {"single", "click", "short_press", "remote_button_short_press", "toggle", "on", "off", "1002", "single_push", "btn_down"}
        double_clicks = {"double", "double_click", "remote_button_double_press", "1004", "double_push"}
        hold_clicks = {"hold", "long_press", "remote_button_long_press", "remote_button_long_release", "1001", "long_push"}

        if desired_action in ("single", "court"):
            return (command in single_clicks) or (click_type in single_clicks)
        elif desired_action in ("double", "double_clic"):
            return (command in double_clicks) or (click_type in double_clicks)
        elif desired_action in ("hold", "long", "maintien"):
            return (command in hold_clicks) or (click_type in hold_clicks)
        else:
            return desired_action.lower() in (command, click_type)

    # -------------------------------------------------------------------------
    # Gestion Anti-Rebond (Debounce) & Modes d'Exécution
    # -------------------------------------------------------------------------
    def _trigger_automation(self, auto_id: str, auto: dict[str, Any], trigger_info: dict[str, Any]) -> None:
        """Valide l'anti-rebond matériel et lance l'exécution selon le mode choisi."""
        now_ts = time_module.time()

        # Anti-rebond (Debounce) matériel : 1000ms par défaut pour boutons physiques
        debounce_ms = float(auto.get("debounce_ms", 1000))
        debounce_seconds = debounce_ms / 1000.0
        last_ts = self._last_triggered_timestamps.get(auto_id, 0.0)

        if (now_ts - last_ts) < debounce_seconds:
            _LOGGER.debug(
                "DomoLink: Déclenchement de '%s' ignoré par l'anti-rebond (%.0f ms restantes)",
                auto.get("name", auto_id),
                (debounce_seconds - (now_ts - last_ts)) * 1000,
            )
            return

        self._last_triggered_timestamps[auto_id] = now_ts

        # Gestion des modes d'exécution (single, restart, queued, parallel)
        mode = auto.get("mode", EXEC_MODE_SINGLE)
        tasks = self._running_tasks.setdefault(auto_id, [])

        # Nettoyer les tâches terminées
        tasks = [t for t in tasks if not t.done()]
        self._running_tasks[auto_id] = tasks

        if tasks and mode == EXEC_MODE_SINGLE:
            _LOGGER.info("DomoLink: Automatisation '%s' déjà en cours d'exécution (mode single) ➔ Ignorée.", auto.get("name", auto_id))
            return

        if tasks and mode == EXEC_MODE_RESTART:
            for t in tasks:
                t.cancel()
            self._running_tasks[auto_id] = []

        task = self.hass.async_create_task(
            self._async_run_automation_flow(auto_id, auto, trigger_info)
        )
        self._running_tasks[auto_id].append(task)

    # -------------------------------------------------------------------------
    # Cheminement d'Exécution Complet (Conditions -> Actions -> Tracing)
    # -------------------------------------------------------------------------
    async def _async_run_automation_flow(
        self,
        auto_id: str,
        auto: dict[str, Any],
        trigger_info: dict[str, Any],
    ) -> bool:
        """Exécute l'enchaînement complet et enregistre la trace d'audit."""
        start_time = dt_util.now()
        start_perf = time_module.perf_counter()

        trace: dict[str, Any] = {
            "automation_id": auto_id,
            "automation_name": auto.get("name", auto_id),
            "timestamp": start_time.isoformat(),
            "trigger": trigger_info,
            "conditions_passed": False,
            "condition_traces": [],
            "action_traces": [],
            "status": "started",
            "duration_ms": 0,
        }

        try:
            # 1. Évaluation des Conditions
            conditions = auto.get("conditions", [])
            cond_mode = auto.get("condition_mode", "and")
            all_passed, condition_traces = self.evaluate_conditions(conditions, cond_mode)

            trace["conditions_passed"] = all_passed
            trace["condition_traces"] = condition_traces

            if not all_passed:
                trace["status"] = "conditions_blocked"
                trace["duration_ms"] = round((time_module.perf_counter() - start_perf) * 1000, 2)
                await self.storage.async_add_automation_trace(trace)
                _LOGGER.info("DomoLink: Automatisation '%s' arrêtée car conditions non remplies.", auto.get("name", auto_id))
                return False

            # 2. Exécution des Actions Séquencées
            actions = auto.get("actions", [])
            for index, action in enumerate(actions):
                act_start = time_module.perf_counter()
                act_type = action.get("type", AUTO_ACTION_SERVICE)

                action_trace: dict[str, Any] = {
                    "step": index + 1,
                    "type": act_type,
                    "action": action,
                    "success": False,
                    "error": None,
                }

                try:
                    # A. Temporisation (Delay)
                    if act_type == AUTO_ACTION_DELAY:
                        seconds = float(action.get("duration", action.get("seconds", 1.0)))
                        _LOGGER.debug("DomoLink: Temporisation de %.1f s...", seconds)
                        await asyncio.sleep(seconds)
                        action_trace["success"] = True

                    # B. Branchement conditionnel (If-Then-Else)
                    elif act_type == AUTO_ACTION_IF_THEN:
                        sub_conds = action.get("conditions", [])
                        sub_mode = action.get("condition_mode", "and")
                        sub_passed, _ = self.evaluate_conditions(sub_conds, sub_mode)

                        branch = "then" if sub_passed else "else"
                        sub_actions = action.get(branch, [])
                        _LOGGER.info("DomoLink: Branchement conditionnel pris: %s", branch)

                        for sub_act in sub_actions:
                            await self._execute_single_action(sub_act)
                        action_trace["success"] = True
                        action_trace["branch"] = branch

                    # C. Action Accès DomoLink (Portail / Porte / Garage) ou Service HA
                    else:
                        success = await self._execute_single_action(action)
                        action_trace["success"] = success

                except asyncio.CancelledError:
                    action_trace["error"] = "Cancelled"
                    raise
                except Exception as err:
                    action_trace["error"] = str(err)
                    _LOGGER.error("DomoLink: Erreur action étape %d: %s", index + 1, err)

                action_trace["duration_ms"] = round((time_module.perf_counter() - act_start) * 1000, 2)
                trace["action_traces"].append(action_trace)

            trace["status"] = "success"
            auto["last_triggered"] = start_time.isoformat()
            auto["trigger_count"] = int(auto.get("trigger_count", 0)) + 1
            await self.storage.async_save_automation(auto_id, auto)

        except asyncio.CancelledError:
            trace["status"] = "cancelled"
            _LOGGER.info("DomoLink: Automatisation '%s' interrompue.", auto.get("name", auto_id))
            return False
        except Exception as err:
            trace["status"] = "error"
            trace["error"] = str(err)
            _LOGGER.error("DomoLink: Erreur lors de l'exécution de '%s': %s", auto.get("name", auto_id), err, exc_info=True)
            return False
        finally:
            trace["duration_ms"] = round((time_module.perf_counter() - start_perf) * 1000, 2)
            await self.storage.async_add_automation_trace(trace)

        return True

    async def _execute_single_action(self, action: dict[str, Any]) -> bool:
        """Exécute une action unitaire (accès DomoLink, service, appareil, notification)."""
        act_type = action.get("type", AUTO_ACTION_SERVICE)
        target_type = action.get("target_type", "entity")
        target_value = action.get("target_value")

        # 1. Contrôle direct d'un Accès DomoLink (Portail, Porte, Garage)
        if act_type == AUTO_ACTION_GATE or target_type == TARGET_TYPE_GATE:
            if not self.coordinator:
                _LOGGER.error("DomoLink: Coordinateur non lié pour exécuter l'action d'accès.")
                return False
            gate_id = action.get("gate_id") or target_value or "gate_1"
            operation = (
                action.get("gate_operation")
                or action.get("operation")
                or action.get("service")
                or "toggle"
            )
            if operation in ("toggle", "trigger"):
                return await self.coordinator.async_gate_trigger_action(mode="toggle", gate_id=gate_id)
            elif operation in ("open", "open_now"):
                return await self.coordinator.async_gate_trigger_action(mode="open", gate_id=gate_id)
            elif operation in ("close", "close_now"):
                return await self.coordinator.async_gate_trigger_action(mode="close", gate_id=gate_id)
            elif operation == "pedestrian":
                return await self.coordinator.async_gate_trigger_action(mode="pedestrian", gate_id=gate_id)
            elif operation == "hold_open":
                dur = int(action.get("duration_minutes") or 60)
                await self.coordinator.async_gate_set_hold_open(True, duration_minutes=dur, gate_id=gate_id)
                return True
            elif operation == "cancel_hold_open":
                await self.coordinator.async_gate_set_hold_open(False, gate_id=gate_id)
                return True
            return await self.coordinator.async_gate_trigger_action(mode="toggle", gate_id=gate_id)

        # 2. Notification directe dans une étape d'automatisation
        if act_type == AUTO_ACTION_NOTIFICATION or target_type == "notification":
            msg = action.get("message") or action.get("service_data", {}).get("message") or "Alerte Automatisation DomoLink"
            notify_srv = target_value or action.get("service") or "notify.persistent_notification"
            try:
                if notify_srv == "notify.persistent_notification" or notify_srv == "persistent":
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {"title": "DomoLink Automatisation", "message": msg},
                        blocking=True,
                    )
                    return True
                srv_name = notify_srv.replace("notify.", "")
                await self.hass.services.async_call(
                    "notify",
                    srv_name,
                    {"message": msg, "title": "DomoLink"},
                    blocking=True,
                )
                return True
            except Exception as err:
                _LOGGER.error("DomoLink: Erreur notification automatisation: %s", err)
                return False

        # 3. Support syntaxe HA native ou directe
        if "target" in action:
            return await self.resolver.execute_action("direct", None, action)

        return await self.resolver.execute_action(target_type, target_value, action)

    # -------------------------------------------------------------------------
    # Évaluation des Conditions (avec Live Dry-Run support)
    # -------------------------------------------------------------------------
    def evaluate_conditions(
        self,
        conditions: list[dict[str, Any]],
        mode: str = "and",
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Évalue les conditions et retourne le résultat global avec les détails de chaque test."""
        if not conditions:
            return True, []

        traces: list[dict[str, Any]] = []
        results: list[bool] = []

        now = dt_util.now()
        country = self.storage.get_settings().get("country", COUNTRY_FR)

        for cond in conditions:
            c_type = cond.get("type", AUTO_COND_STATE)
            passed = False
            reason = ""

            # 1. Condition État d'une entité
            if c_type == AUTO_COND_STATE:
                entity_id = cond.get("entity_id")
                expected = cond.get("state")
                state_obj = self.hass.states.get(entity_id) if entity_id else None
                curr_val = state_obj.state if state_obj else None

                if curr_val is not None and str(curr_val).lower() == str(expected).lower():
                    passed = True
                    reason = f"{entity_id} est bien à '{curr_val}'"
                else:
                    passed = False
                    reason = f"{entity_id} vaut '{curr_val}', attendu '{expected}'"

            # 2. Condition Seuil Numérique
            elif c_type == AUTO_COND_NUMERIC_STATE:
                entity_id = cond.get("entity_id")
                state_obj = self.hass.states.get(entity_id) if entity_id else None
                try:
                    num_val = float(state_obj.state) if state_obj else 0.0
                    above = cond.get("above")
                    below = cond.get("below")

                    p_above = True if (above is None or str(above) == "") else num_val > float(above)
                    p_below = True if (below is None or str(below) == "") else num_val < float(below)

                    passed = p_above and p_below
                    reason = f"{entity_id} = {num_val} (plage attendue: >{above} et <{below})"
                except Exception as err:
                    passed = False
                    reason = f"Valeur non numérique pour {entity_id}: {err}"

            # 3. Condition Plage Horaire (supporte le passage de minuit ex: 22:00 -> 06:00)
            elif c_type == AUTO_COND_TIME_WINDOW:
                after_str = cond.get("after")
                before_str = cond.get("before")
                curr_t = now.time()

                t_after: time | None = None
                t_before: time | None = None

                if after_str:
                    parts = [int(p) for p in after_str.split(":")[:2]]
                    t_after = time(parts[0], parts[1])

                if before_str:
                    parts = [int(p) for p in before_str.split(":")[:2]]
                    t_before = time(parts[0], parts[1])

                if t_after is not None and t_before is not None:
                    if t_after <= t_before:
                        passed = t_after <= curr_t <= t_before
                    else:
                        # Plage traversant minuit (ex: 22:00 -> 06:00)
                        passed = curr_t >= t_after or curr_t <= t_before
                elif t_after is not None:
                    passed = curr_t >= t_after
                elif t_before is not None:
                    passed = curr_t <= t_before
                else:
                    passed = True

                reason = f"Heure actuelle {curr_t.strftime('%H:%M')} dans l'intervalle [{after_str or '00:00'} - {before_str or '23:59'}]"

            # 4. Condition Jours Fériés (Moteur Offline DomoLink)
            elif c_type == AUTO_COND_HOLIDAY:
                h_mode = cond.get("mode", HOLIDAY_MODE_EXCLUDE)
                is_holiday = HolidayEngine.is_holiday(now.date(), country)
                h_name = HolidayEngine.get_holiday_name(now.date(), country) or "Jour férié"

                if h_mode == HOLIDAY_MODE_EXCLUDE:
                    passed = not is_holiday
                    reason = f"Jour ouvré (Exclusion jour férié '{h_name}')" if not is_holiday else f"Aujourd'hui est un jour férié ({h_name})"
                elif h_mode == HOLIDAY_MODE_ONLY:
                    passed = is_holiday
                    reason = f"Jour férié validé ({h_name})" if is_holiday else "Aujourd'hui n'est pas un jour férié"
                else:
                    passed = True
                    reason = "Mode férié actif"

            # 5. Condition Présence
            elif c_type == AUTO_COND_PRESENCE:
                p_mode = cond.get("mode", "home")
                p_ent = cond.get("entity_id") or self.storage.get_settings().get("presence_entity")
                st = self.hass.states.get(p_ent) if p_ent else None
                is_home = st.state in (STATE_HOME, STATE_ON, "true") if st else False

                if p_mode == "home":
                    passed = is_home
                    reason = "Présence confirmée" if is_home else "Absence constatée"
                else:
                    passed = not is_home
                    reason = "Absence confirmée" if not is_home else "Présence constatée"

            # 6. Condition Alarme
            elif c_type == AUTO_COND_ALARM:
                a_mode = cond.get("mode", "disarmed")
                a_ent = cond.get("entity_id") or self.storage.get_settings().get("alarm_entity")
                st = self.hass.states.get(a_ent) if a_ent else None
                is_disarmed = st.state in ("disarmed", STATE_OFF) if st else True

                if a_mode == "disarmed":
                    passed = is_disarmed
                    reason = "Alarme désarmée" if is_disarmed else f"Alarme armée ({st.state if st else 'N/A'})"
                else:
                    passed = not is_disarmed
                    reason = "Alarme armée" if not is_disarmed else "Alarme désarmée"

            # 7. Condition Soleil (Position au-dessus ou sous l'horizon)
            elif c_type == AUTO_COND_SUN:
                sun_st = self.hass.states.get("sun.sun")
                expected_sun = cond.get("state", "above_horizon")
                curr_sun = sun_st.state if sun_st else "unknown"
                passed = curr_sun == expected_sun
                reason = f"Soleil: {curr_sun} (attendu: {expected_sun})"

            results.append(passed)
            traces.append({
                "type": c_type,
                "passed": passed,
                "reason": reason,
                "config": cond,
            })

        if mode == "or":
            final_result = any(results)
        else:
            final_result = all(results)

        return final_result, traces
