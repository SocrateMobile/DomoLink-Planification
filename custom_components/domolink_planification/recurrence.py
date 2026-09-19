"""Moteur d'évaluation des récurrences, dates et déclencheurs pour DomoLink-Planification."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

try:
    from .const import (
        DATE_MODE_EXACT_DAY,
        DATE_MODE_WEEKDAYS,
        RECURRENCE_DATE,
        RECURRENCE_EVERY,
        RECURRENCE_NEXT,
        TIME_TYPE_FIXED,
        TIME_TYPE_SUNRISE,
        TIME_TYPE_SUNSET,
        TRIGGER_TYPE_SOLAR,
        TRIGGER_TYPE_TIME,
    )
except (ImportError, ValueError):
    from const import (
        DATE_MODE_EXACT_DAY,
        DATE_MODE_WEEKDAYS,
        RECURRENCE_DATE,
        RECURRENCE_EVERY,
        RECURRENCE_NEXT,
        TIME_TYPE_FIXED,
        TIME_TYPE_SUNRISE,
        TIME_TYPE_SUNSET,
        TRIGGER_TYPE_SOLAR,
        TRIGGER_TYPE_TIME,
    )


class RecurrenceEngine:
    """Moteur pur Python de calcul et de vérification des dates de déclenchement."""

    @staticmethod
    def check_trigger_match(sched: dict[str, Any], now: datetime, sun_target_time: datetime | None = None) -> bool:
        """Vérifie si la date et l'heure courantes correspondent à la planification."""
        time_type = sched.get("time_type", TIME_TYPE_FIXED)
        trigger_type = sched.get("trigger_type", TRIGGER_TYPE_TIME)

        # 1. Vérification de l'heure
        if time_type in (TIME_TYPE_SUNRISE, TIME_TYPE_SUNSET) or trigger_type == TRIGGER_TYPE_SOLAR:
            if not sun_target_time:
                return False
            if now.hour != sun_target_time.hour or now.minute != sun_target_time.minute:
                return False
        else:
            time_str = sched.get("time", "00:00")
            try:
                target_h, target_m = [int(p) for p in time_str.split(":")[:2]]
                if now.hour != target_h or now.minute != target_m:
                    return False
            except Exception:
                return False

        # 2. Vérification de la fréquence / récurrence
        rec_mode = sched.get("recurrence_mode", RECURRENCE_EVERY)

        if rec_mode in (RECURRENCE_EVERY, RECURRENCE_NEXT):
            weekdays = sched.get("weekdays")
            if weekdays is not None and len(weekdays) > 0:
                if now.weekday() not in weekdays:
                    return False
            return True

        if rec_mode == RECURRENCE_DATE:
            # Mois (1..12)
            target_month = sched.get("month")
            if target_month is not None and str(target_month) != "":
                if now.month != int(target_month):
                    return False

            # Année (fixe ou "every_year")
            target_year = sched.get("year")
            if target_year is not None and str(target_year) != "every_year" and str(target_year) != "":
                if now.year != int(target_year):
                    return False

            # Jour précis OU jours de semaine
            date_type = sched.get("date_selection_type", DATE_MODE_EXACT_DAY)
            if date_type == DATE_MODE_EXACT_DAY:
                target_day = sched.get("day_of_month")
                if target_day is not None and str(target_day) != "":
                    if now.day != int(target_day):
                        return False
            elif date_type == DATE_MODE_WEEKDAYS:
                weekdays = sched.get("weekdays")
                if weekdays is not None and len(weekdays) > 0:
                    if now.weekday() not in weekdays:
                        return False

            return True

        return True

    @staticmethod
    def compute_next_run(sched: dict[str, Any], now: datetime) -> str | None:
        """Calcule la prochaine date/heure d'exécution (format ISO) pour une règle."""
        if not sched.get("enabled", True) or sched.get("is_completed", False):
            return None

        time_str = sched.get("time", "00:00")
        try:
            h, m = [int(p) for p in time_str.split(":")[:2]]
        except Exception:
            h, m = 0, 0

        rec_mode = sched.get("recurrence_mode", RECURRENCE_EVERY)

        if rec_mode in (RECURRENCE_EVERY, RECURRENCE_NEXT):
            weekdays = sched.get("weekdays") or [0, 1, 2, 3, 4, 5, 6]
            for day_offset in range(14):
                candidate_dt = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=day_offset)
                if candidate_dt > now and candidate_dt.weekday() in weekdays:
                    return candidate_dt.isoformat()
            return None

        if rec_mode == RECURRENCE_DATE:
            target_month = sched.get("month")
            target_year = sched.get("year")
            date_type = sched.get("date_selection_type", DATE_MODE_EXACT_DAY)
            weekdays = sched.get("weekdays") or [0, 1, 2, 3, 4, 5, 6]
            day_of_month = sched.get("day_of_month")

            for day_offset in range(400):
                candidate_dt = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=day_offset)
                if candidate_dt <= now:
                    continue

                if target_month is not None and str(target_month) != "" and candidate_dt.month != int(target_month):
                    continue

                if target_year is not None and str(target_year) != "every_year" and str(target_year) != "":
                    if candidate_dt.year != int(target_year):
                        continue

                if date_type == DATE_MODE_EXACT_DAY:
                    if day_of_month is not None and str(day_of_month) != "" and candidate_dt.day != int(day_of_month):
                        continue
                elif date_type == DATE_MODE_WEEKDAYS:
                    if candidate_dt.weekday() not in weekdays:
                        continue

                return candidate_dt.isoformat()

            return None

        return None
