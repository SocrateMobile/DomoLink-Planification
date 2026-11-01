"""Tests unitaires pour le moteur d'automatisations modernes de DomoLink-Planification."""

import unittest
from datetime import date, datetime, time
import sys
import types
from unittest.mock import MagicMock

# Si homeassistant n'est pas présent dans l'environnement Python local, le mocker proprement
if "homeassistant" not in sys.modules:
    ha_mock = types.ModuleType("homeassistant")
    ha_mock.__path__ = []

    ha_const = types.ModuleType("homeassistant.const")
    ha_const.EVENT_STATE_CHANGED = "state_changed"
    ha_const.STATE_HOME = "home"
    ha_const.STATE_NOT_HOME = "not_home"
    ha_const.STATE_ON = "on"
    ha_const.STATE_OFF = "off"
    ha_const.STATE_UNAVAILABLE = "unavailable"
    ha_const.STATE_UNKNOWN = "unknown"

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.Event = MagicMock()
    ha_core.HomeAssistant = MagicMock()
    ha_core.ServiceCall = MagicMock()
    ha_core.callback = lambda f: f

    ha_util = types.ModuleType("homeassistant.util")
    ha_util_dt = types.ModuleType("homeassistant.util.dt")
    ha_util_dt.now = datetime.now
    ha_util.dt = ha_util_dt

    ha_components = types.ModuleType("homeassistant.components")
    ha_components.__path__ = []
    ha_frontend = types.ModuleType("homeassistant.components.frontend")
    ha_http = types.ModuleType("homeassistant.components.http")
    ha_http.HomeAssistantView = MagicMock
    ha_components.frontend = ha_frontend
    ha_components.http = ha_http

    ha_config_entries = types.ModuleType("homeassistant.config_entries")
    ha_config_entries.ConfigEntry = MagicMock

    ha_exceptions = types.ModuleType("homeassistant.exceptions")
    ha_exceptions.Unauthorized = Exception

    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers.__path__ = []
    ha_helpers_storage = types.ModuleType("homeassistant.helpers.storage")
    ha_helpers_storage.Store = MagicMock()
    ha_helpers.storage = ha_helpers_storage
    ha_helpers.config_validation = MagicMock()

    ha_helpers_service = types.ModuleType("homeassistant.helpers.service")
    ha_helpers_service.async_register_admin_service = MagicMock()
    ha_helpers.service = ha_helpers_service

    ha_helpers_event = types.ModuleType("homeassistant.helpers.event")
    ha_helpers_event.async_track_time_interval = MagicMock()
    ha_helpers.event = ha_helpers_event


    class MockDataUpdateCoordinator:
        def __class_getitem__(cls, item):
            return cls
        def __init__(self, *args, **kwargs):
            pass

    ha_helpers_coord = types.ModuleType("homeassistant.helpers.update_coordinator")
    ha_helpers_coord.DataUpdateCoordinator = MockDataUpdateCoordinator
    ha_helpers.update_coordinator = ha_helpers_coord


    ha_helpers.area_registry = MagicMock()
    ha_helpers.device_registry = MagicMock()
    ha_helpers.entity_registry = MagicMock()
    ha_helpers.label_registry = MagicMock()

    sys.modules["homeassistant"] = ha_mock
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.util"] = ha_util
    sys.modules["homeassistant.util.dt"] = ha_util_dt
    sys.modules["homeassistant.components"] = ha_components
    sys.modules["homeassistant.components.frontend"] = ha_frontend
    sys.modules["homeassistant.components.http"] = ha_http
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.exceptions"] = ha_exceptions
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.service"] = ha_helpers_service
    sys.modules["homeassistant.helpers.storage"] = ha_helpers_storage

    sys.modules["homeassistant.helpers.config_validation"] = ha_helpers.config_validation
    sys.modules["homeassistant.helpers.event"] = ha_helpers_event
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_helpers_coord
    sys.modules["homeassistant.helpers.area_registry"] = ha_helpers.area_registry
    sys.modules["homeassistant.helpers.device_registry"] = ha_helpers.device_registry
    sys.modules["homeassistant.helpers.entity_registry"] = ha_helpers.entity_registry
    sys.modules["homeassistant.helpers.label_registry"] = ha_helpers.label_registry




import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.domolink_planification.automation_engine import AutomationEngine
from custom_components.domolink_planification.const import (
    AUTO_COND_HOLIDAY,
    AUTO_COND_NUMERIC_STATE,
    AUTO_COND_STATE,
    AUTO_COND_TIME_WINDOW,
    AUTO_TRIGGER_BUTTON,
    AUTO_TRIGGER_EVENT,
    HOLIDAY_MODE_EXCLUDE,
    HOLIDAY_MODE_ONLY,
)



class TestAutomationEngine(unittest.TestCase):
    """Vérification des briques logiques du moteur d'automatisations."""

    def test_match_dict_subset(self):
        """Vérifie le filtrage récursif et flexible des données d'événements."""
        target = {
            "device_id": "dbe1f8c50e85cbfe2b760c5915445a21",
            "command": "single",
            "cluster_id": 6,
            "args": {"attribute_id": 0, "click_type": "single"},
        }

        # Match exact sur device_id
        pattern1 = {"device_id": "dbe1f8c50e85cbfe2b760c5915445a21"}
        self.assertTrue(AutomationEngine._match_dict_subset(pattern1, target))

        # Match avec clé imbriquée
        pattern2 = {"args": {"click_type": "single"}}
        self.assertTrue(AutomationEngine._match_dict_subset(pattern2, target))

        # Rejet sur mauvaise valeur
        pattern3 = {"device_id": "autre_device"}
        self.assertFalse(AutomationEngine._match_dict_subset(pattern3, target))

    def test_match_button_trigger_xiaomi(self):
        """Vérifie la reconnaissance intelligente des boutons Xiaomi / Aqara."""
        # Cas 1 : Appui simple classique (command: single)
        event1 = {
            "device_id": "dbe1f8c50e85cbfe2b760c5915445a21",
            "command": "single",
            "args": {"attribute_id": 0},
        }
        trigger_single = {
            "device_id": "dbe1f8c50e85cbfe2b760c5915445a21",
            "action": "single",
        }
        self.assertTrue(AutomationEngine._match_button_trigger(trigger_single, "zha_event", event1))

        # Cas 2 : Appui simple via arguments (click_type: single)
        event2 = {
            "device_id": "dbe1f8c50e85cbfe2b760c5915445a21",
            "command": "attribute_updated",
            "args": {"click_type": "single"},
        }
        self.assertTrue(AutomationEngine._match_button_trigger(trigger_single, "zha_event", event2))

        # Cas 3 : Appui long (Remote Button Long Press)
        event3 = {
            "device_id": "dbe1f8c50e85cbfe2b760c5915445a21",
            "command": "remote_button_long_press",
        }
        trigger_hold = {
            "device_id": "dbe1f8c50e85cbfe2b760c5915445a21",
            "action": "hold",
        }
        self.assertTrue(AutomationEngine._match_button_trigger(trigger_hold, "zha_event", event3))
        # Doit être rejeté si on attendait un appui court
        self.assertFalse(AutomationEngine._match_button_trigger(trigger_single, "zha_event", event3))

        # Cas 4 : Mode 'any' (N'importe quel appui déclenche)
        trigger_any = {
            "device_id": "dbe1f8c50e85cbfe2b760c5915445a21",
            "action": "any",
        }
        self.assertTrue(AutomationEngine._match_button_trigger(trigger_any, "zha_event", event1))
        self.assertTrue(AutomationEngine._match_button_trigger(trigger_any, "zha_event", event3))

    def test_condition_evaluation(self):
        """Vérifie l'évaluation en direct des conditions avec mock Home Assistant."""
        mock_hass = MagicMock()
        mock_storage = MagicMock()
        mock_storage.get_settings.return_value = {"country": "FR"}
        mock_resolver = MagicMock()

        engine = AutomationEngine(mock_hass, mock_storage, mock_resolver)

        # Configurer l'état mocké d'un capteur de portail
        mock_state = MagicMock()
        mock_state.state = "closed"
        mock_hass.states.get.return_value = mock_state

        conditions = [
            {
                "type": AUTO_COND_STATE,
                "entity_id": "binary_sensor.portail",
                "state": "closed",
            }
        ]
        passed, traces = engine.evaluate_conditions(conditions, "and")
        self.assertTrue(passed)
        self.assertEqual(len(traces), 1)
        self.assertTrue(traces[0]["passed"])

        # Condition rejetée si état différent
        conditions_fail = [
            {
                "type": AUTO_COND_STATE,
                "entity_id": "binary_sensor.portail",
                "state": "open",
            }
        ]
        passed_fail, _ = engine.evaluate_conditions(conditions_fail, "and")
        self.assertFalse(passed_fail)

    def test_condition_numeric_state(self):
        """Vérifie la condition sur seuil numérique (ex: capteur de température ou luminosité)."""
        mock_hass = MagicMock()
        mock_storage = MagicMock()
        mock_storage.get_settings.return_value = {"country": "FR"}
        mock_resolver = MagicMock()

        engine = AutomationEngine(mock_hass, mock_storage, mock_resolver)

        mock_state = MagicMock()
        mock_state.state = "22.5"
        mock_hass.states.get.return_value = mock_state

        conds = [
            {
                "type": AUTO_COND_NUMERIC_STATE,
                "entity_id": "sensor.temperature_ext",
                "above": 20.0,
                "below": 25.0,
            }
        ]
        passed, traces = engine.evaluate_conditions(conds, "and")
        self.assertTrue(passed)

        # Seuil non respecté
        conds_fail = [
            {
                "type": AUTO_COND_NUMERIC_STATE,
                "entity_id": "sensor.temperature_ext",
                "above": 25.0,
            }
        ]
        passed_fail, _ = engine.evaluate_conditions(conds_fail, "and")
        self.assertFalse(passed_fail)

    def test_debounce_mechanism(self):
        """Vérifie que l'anti-rebond matériel bloque les doubles appuis instantanés."""
        mock_hass = MagicMock()
        mock_hass.async_create_task = MagicMock()
        mock_storage = MagicMock()
        mock_storage.get_settings.return_value = {"country": "FR"}
        mock_resolver = MagicMock()

        engine = AutomationEngine(mock_hass, mock_storage, mock_resolver)

        auto_id = "test_auto_button"
        auto_data = {
            "name": "Bouton Portail",
            "debounce_ms": 1500, # 1.5s d'anti-rebond
            "mode": "single",
            "conditions": [],
            "actions": [],
        }

        trigger_info = {"trigger_type": "button"}

        # 1er appui -> doit être exécuté
        engine._trigger_automation(auto_id, auto_data, trigger_info)
        self.assertEqual(mock_hass.async_create_task.call_count, 1)

        # 2e appui immédiat (dans les 10ms) -> doit être bloqué par le debounce
        engine._trigger_automation(auto_id, auto_data, trigger_info)
        self.assertEqual(mock_hass.async_create_task.call_count, 1) # toujours 1 !

        # 3e appui après expiration du debounce -> doit passer
        engine._last_triggered_timestamps[auto_id] -= 2.0
        engine._trigger_automation(auto_id, auto_data, trigger_info)
        self.assertEqual(mock_hass.async_create_task.call_count, 2)

        # Nettoyage des coroutines mockées pour éviter tout RuntimeWarning
        for call_args in mock_hass.async_create_task.call_args_list:
            coro = call_args[0][0]
            coro.close()




if __name__ == "__main__":
    unittest.main()
