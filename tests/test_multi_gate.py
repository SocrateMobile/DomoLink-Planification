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
)
from custom_components.domolink_planification.storage import PlanificationStorage


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


if __name__ == "__main__":
    unittest.main()
