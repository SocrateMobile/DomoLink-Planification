"""Gestion bioclimatique solaire et suivi de trajectoire pour volets roulants."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

try:
    from .const import (
        COMPASS_AZIMUTH,
        COMPASS_S,
        SHADING_MODE_SUMMER,
        SHADING_MODE_WINTER,
    )
except (ImportError, ValueError):
    from const import (
        COMPASS_AZIMUTH,
        COMPASS_S,
        SHADING_MODE_SUMMER,
        SHADING_MODE_WINTER,
    )

_LOGGER = logging.getLogger(__name__)


def resolve_azimuth(orientation: str | float | int) -> float:
    """Convertit une orientation boussole (ex: 'S', 'SE', 'NNE') ou un nombre en azimut (0-360°)."""
    if isinstance(orientation, (int, float)):
        return float(orientation) % 360.0
    key = str(orientation).strip().upper()
    if key in COMPASS_AZIMUTH:
        return COMPASS_AZIMUTH[key]
    try:
        return float(key) % 360.0
    except ValueError:
        _LOGGER.warning("Orientation inconnue '%s', valeur par défaut Sud (180°) utilisée", orientation)
        return 180.0


def calculate_solar_incidence(facade_azimuth: float, sun_azimuth: float) -> float:
    """Calcule l'angle d'incidence entre la normale de la fenêtre et le soleil (0° à 180°)."""
    diff = abs(sun_azimuth - facade_azimuth) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return round(diff, 1)


def is_sun_striking_window(
    facade_azimuth: float,
    sun_azimuth: float,
    sun_elevation: float,
    cone_angle: float = 60.0,
    min_elevation: float = 5.0,
    max_elevation: float = 85.0,
) -> tuple[bool, float]:
    """Détermine si le soleil frappe directement la vitre de la façade."""
    if sun_elevation < min_elevation or sun_elevation > max_elevation:
        return False, calculate_solar_incidence(facade_azimuth, sun_azimuth)

    incidence = calculate_solar_incidence(facade_azimuth, sun_azimuth)
    striking = incidence <= cone_angle
    return striking, incidence


class SolarShadingEvaluator:
    """Évaluateur d'état et de position pour volets roulants selon le soleil et la température."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    def evaluate_rule(
        self,
        rule_config: dict[str, Any],
        last_action_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Évalue une règle de volet solaire et détermine l'action à exécuter."""
        cover_id = rule_config.get("cover_entity_id")
        orientation = rule_config.get("orientation", COMPASS_S)
        facade_azimuth = resolve_azimuth(orientation)
        temp_sensor_id = rule_config.get("temperature_sensor_id")
        temp_threshold = float(rule_config.get("temperature_threshold", 24.0))
        shading_pos = int(rule_config.get("shading_position", 20))
        open_pos = int(rule_config.get("open_position", 100))
        mode = rule_config.get("mode", SHADING_MODE_SUMMER)
        cone_angle = float(rule_config.get("cone_angle", 60.0))
        min_elev = float(rule_config.get("min_elevation", 5.0))
        max_elev = float(rule_config.get("max_elevation", 85.0))

        # 1. Vérifier l'état du soleil dans Home Assistant
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            return {
                "should_act": False,
                "reason": "Entité sun.sun indisponible dans Home Assistant",
                "target_position": None,
                "in_sun": False,
            }

        sun_azimuth = float(sun_state.attributes.get("azimuth", 0.0))
        sun_elevation = float(sun_state.attributes.get("elevation", -90.0))

        # 2. Vérifier si le soleil frappe la vitre
        striking, incidence = is_sun_striking_window(
            facade_azimuth=facade_azimuth,
            sun_azimuth=sun_azimuth,
            sun_elevation=sun_elevation,
            cone_angle=cone_angle,
            min_elevation=min_elev,
            max_elevation=max_elev,
        )

        # 3. Vérifier la température
        current_temp: float | None = None
        if temp_sensor_id:
            sensor_state = self.hass.states.get(temp_sensor_id)
            if sensor_state and sensor_state.state not in ("unknown", "unavailable"):
                try:
                    current_temp = float(sensor_state.state)
                except (ValueError, TypeError):
                    current_temp = None

        # 4. Décision selon le mode (Été / Hiver)
        target_pos: int | None = None
        should_shade = False
        reason = ""

        if mode == SHADING_MODE_SUMMER:
            # Confort d'été : Fermer pour protéger de la surchauffe
            temp_condition = (current_temp is None) or (current_temp >= temp_threshold)
            if striking and temp_condition:
                should_shade = True
                target_pos = shading_pos
                temp_str = f"{current_temp}°C" if current_temp is not None else "N/A"
                reason = (
                    f"☀️ Protection solaire active (Façade {orientation}/{facade_azimuth}°, "
                    f"Soleil azimut {sun_azimuth}° / élév. {sun_elevation}°, incidence {incidence}°, "
                    f"Temp {temp_str} >= {temp_threshold}°C) ➔ Fermeture à {shading_pos}%"
                )
            else:
                should_shade = False
                target_pos = open_pos
                if not striking:
                    reason = (
                        f"🌤️ Soleil hors du cône d'exposition (Incidence {incidence}° > {cone_angle}° "
                        f"ou élévation {sun_elevation}°) ➔ Réouverture à {open_pos}%"
                    )
                else:
                    reason = (
                        f"🌡️ Température clémente ({current_temp}°C < {temp_threshold}°C) ➔ Maintien ouvert à {open_pos}%"
                    )

        else:
            # Confort d'hiver : Ouvrir si soleil présent pour capter la chaleur gratuite, fermer la nuit
            if striking:
                should_shade = False
                target_pos = open_pos
                reason = f"❄️ Gain solaire d'hiver : Soleil direct ➔ Ouverture maximale à {open_pos}%"
            else:
                should_shade = True
                target_pos = shading_pos
                reason = f"❄️ Isolation d'hiver : Absence de soleil direct ➔ Fermeture isolante à {shading_pos}%"

        # 5. Comparer avec la position actuelle du volet pour éviter les commandes inutiles
        cover_state = self.hass.states.get(cover_id) if cover_id else None
        current_cover_pos = None
        if cover_state and "current_position" in cover_state.attributes:
            current_cover_pos = cover_state.attributes.get("current_position")

        should_act = True
        if current_cover_pos is not None and target_pos is not None:
            # Si le volet est déjà à ±2% de la position cible, ne rien faire
            if abs(current_cover_pos - target_pos) <= 2:
                should_act = False

        # Si l'état d'ombrage n'a pas changé depuis la dernière action, respecter l'anti-battement
        if last_action_state and last_action_state.get("should_shade") == should_shade:
            should_act = False

        return {
            "cover_entity_id": cover_id,
            "facade_azimuth": facade_azimuth,
            "sun_azimuth": sun_azimuth,
            "sun_elevation": sun_elevation,
            "incidence_angle": incidence,
            "is_striking": striking,
            "current_temp": current_temp,
            "temp_threshold": temp_threshold,
            "should_shade": should_shade,
            "target_position": target_pos,
            "current_position": current_cover_pos,
            "should_act": should_act,
            "reason": reason,
        }
