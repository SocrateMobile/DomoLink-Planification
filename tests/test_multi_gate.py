"""Tests unitaires pour la gestion multi-accès (portails, portes, garages) et nouveaux types d'ouverture."""

import asyncio
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, AsyncMock

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

    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers.__path__ = []
    ha_helpers_storage = types.ModuleType("homeassistant.helpers.storage")
    ha_helpers_storage.Store = MagicMock()
    ha_helpers.storage = ha_helpers_storage

    sys.modules["homeassistant"] = ha_mock
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.storage"] = ha_helpers_storage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.domolink_planification.const import (
    GATE_TYPE_SLIDING,
    GATE_TYPE_DOUBLE_SWING,
    GATE_TYPE_SINGLE_SWING,
    GATE_TYPE_DOOR,
    GATE_TYPE_GARAGE,
    DEFAULT_GATE_CONFIG,
    AUTO_COND_TIME_WINDOW,
    AUTO_ACTION_GATE,
)
from custom_components.domolink_planification.storage import PlanificationStorage
from custom_components.domolink_planification.recurrence import RecurrenceEngine
from custom_components.domolink_planification.solar_shading import SolarShadingEvaluator
from datetime import datetime, date, timedelta


class TestMultiGateStorage(unittest.IsolatedAsyncioTestCase):
    """Vérification du stockage multi-accès et compatibilité ascendante."""

    async def asyncSetUp(self):
        self.mock_hass = MagicMock()
        self.storage = PlanificationStorage(self.mock_hass)
        # Mock du Store HA
        self.storage._store = MagicMock()
        self.storage._store.async_load = AsyncMock(return_value={
            "schedules": {},
            "history": [],
            "settings": {},
            "gate": {
                "id": "gate_1",
                "name": "Portail Principal",
                "gate_type": GATE_TYPE_SLIDING,
                "travel_time": 15,
                "switch_entity": "switch.shelly_ouverture_portail_voiture",
                "sensor_entity": "binary_sensor.etat_du_portail",
            },
            "gates": {},
            "gate_history": [],
            "automations": {},
            "automation_traces": [],
        })
        self.storage._store.async_save = AsyncMock()

    async def test_migration_legacy_gate_to_gates(self):
        """Vérifie que la configuration 'gate' existante est bien migrée dans 'gates'."""
        data = await self.storage.async_load()
        gates = self.storage.get_gates()
        self.assertIn("gate_1", gates)
        self.assertEqual(gates["gate_1"]["name"], "Portail Principal")
        self.assertEqual(gates["gate_1"]["gate_type"], GATE_TYPE_SLIDING)

    async def test_add_porte_and_garage(self):
        """Vérifie la création d'une porte piétonne et d'une porte de garage."""
        await self.storage.async_load()

        # Ajouter une porte / portillon
        porte_cfg = {
            "id": "door_pedestrian",
            "name": "Portillon Rue",
            "gate_type": GATE_TYPE_DOOR,
            "travel_time": 5,
            "switch_entity": "switch.gache_portillon",
            "sensor_entity": "binary_sensor.portillon_contact",
        }
        await self.storage.async_save_gate("door_pedestrian", porte_cfg)

        # Ajouter une porte de garage
        garage_cfg = {
            "id": "garage_north",
            "name": "Porte de Garage Nord",
            "gate_type": GATE_TYPE_GARAGE,
            "travel_time": 12,
            "switch_entity": "cover.garage_door",
            "switch_type": "cover",
            "sensor_entity": "binary_sensor.garage_magnet",
        }
        await self.storage.async_save_gate("garage_north", garage_cfg)

        gates = self.storage.get_gates()
        self.assertEqual(len(gates), 3)
        self.assertIn("gate_1", gates)
        self.assertIn("door_pedestrian", gates)
        self.assertIn("garage_north", gates)

        # Récupération spécifique
        retrieved_door = self.storage.get_gate_config("door_pedestrian")
        self.assertEqual(retrieved_door["gate_type"], GATE_TYPE_DOOR)
        self.assertEqual(retrieved_door["name"], "Portillon Rue")

        retrieved_garage = self.storage.get_gate_config("garage_north")
        self.assertEqual(retrieved_garage["gate_type"], GATE_TYPE_GARAGE)
        self.assertEqual(retrieved_garage["switch_type"], "cover")

    async def test_delete_gate(self):
        """Vérifie la suppression d'un élément d'accès."""
        await self.storage.async_load()
        await self.storage.async_save_gate("door_temp", {
            "id": "door_temp",
            "name": "Porte Temporaire",
            "gate_type": GATE_TYPE_DOOR,
        })
        self.assertIn("door_temp", self.storage.get_gates())

        success = await self.storage.async_delete_gate("door_temp")
        self.assertTrue(success)
        self.assertNotIn("door_temp", self.storage.get_gates())

    def test_daily_jitter_determinism(self):
        """Vérifie que le Jitter de simulation de présence est déterministe par jour et borné."""
        sched = {
            "id": "sched_presence_1",
            "random_jitter_minutes": 15,
            "time_type": "fixed",
            "time": "20:00",
            "recurrence_mode": "every",
            "weekdays": [0, 1, 2, 3, 4, 5, 6],
        }
        d1 = date(2026, 11, 2)
        j1 = RecurrenceEngine.get_daily_jitter_minutes(sched, d1)
        j2 = RecurrenceEngine.get_daily_jitter_minutes(sched, d1)
        self.assertEqual(j1, j2)
        self.assertTrue(-15 <= j1 <= 15)

        # Vérifie que compute_next_run et check_trigger_match tombent exactement sur la même minute
        base_dt = datetime(2026, 11, 2, 20, 0) + timedelta(minutes=j1)
        self.assertTrue(RecurrenceEngine.check_trigger_match(sched, base_dt))

    def test_solar_shading_override_and_wind_safety(self):
        """Vérifie la dérogation manuelle, la sérialisation ISO et l'alerte vent."""
        mock_hass = MagicMock()

        def get_state(entity_id):
            st = MagicMock()
            if entity_id == "sun.sun":
                st.state = "above_horizon"
                st.attributes = {"azimuth": 180.0, "elevation": 45.0}
                return st
            if entity_id == "cover.volet_salon":
                # L'utilisateur a bougé le volet manuellement à 65% alors que la dernière commande était 20%
                st.state = "open"
                st.attributes = {"current_position": 65}
                return st
            if entity_id == "sensor.vent":
                st.state = "55"
                st.attributes = {}
                return st
            return None

        mock_hass.states.get = get_state
        engine = SolarShadingEvaluator(mock_hass)

        rule = {
            "id": "solar_1",
            "cover_entity_id": "cover.volet_salon",
            "orientation": "S",
            "mode": "summer",
            "shading_position": 20,
            "open_position": 100,
            "manual_override_minutes": 120,
            "wind_speed_threshold": 0,
        }
        now = datetime(2026, 7, 15, 14, 0)
        prev_state = {"is_shaded": True, "last_commanded_pos": 20, "unshaded_since": now.isoformat()}

        res = engine.evaluate_rule(rule, prev_state, now=now)
        self.assertTrue(res["manual_override"])
        self.assertFalse(res["should_act"])
        self.assertEqual(res["current_position"], 65)

        # Test sécurité vent prioritaire sur tout
        rule["wind_speed_threshold"] = 45
        rule["wind_sensor_entity"] = "sensor.vent"
        res_wind = engine.evaluate_rule(rule, res, now=now)
        self.assertTrue(res_wind["wind_alert"])
        self.assertEqual(res_wind["target_position"], 100)
        self.assertFalse(res_wind["manual_override"])


if __name__ == "__main__":
    unittest.main()
