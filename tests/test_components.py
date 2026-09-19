"""Tests unitaires pour les calculs de jours fériés et de suivi solaire."""

import unittest
from datetime import date, datetime

import sys
import os

# Ajouter le chemin du composant pour importer les modules de calcul
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "domolink_planification")))

from holidays import (
    HolidayEngine,
    calculate_easter_gregorian,
    calculate_easter_orthodox,
)
from solar_shading import (
    calculate_solar_incidence,
    is_sun_striking_window,
    resolve_azimuth,
)


class TestHolidays(unittest.TestCase):
    """Vérification des calculs de jours fériés pour les 7 pays."""

    def test_easter_2026(self):
        easter_2026 = calculate_easter_gregorian(2026)
        self.assertEqual(easter_2026, date(2026, 4, 5))

    def test_easter_orthodox_2026(self):
        easter_orth_2026 = calculate_easter_orthodox(2026)
        self.assertEqual(easter_orth_2026.month, 4)

    def test_france_holidays_2026(self):
        hols = HolidayEngine.get_holidays(2026, "FR")
        self.assertIn(date(2026, 1, 1), hols)
        self.assertIn(date(2026, 5, 1), hols)
        self.assertIn(date(2026, 7, 14), hols)
        self.assertIn(date(2026, 12, 25), hols)
        self.assertTrue(HolidayEngine.is_holiday(date(2026, 7, 14), "FR"))
        self.assertFalse(HolidayEngine.is_holiday(date(2026, 7, 15), "FR"))

    def test_usa_holidays_2026(self):
        hols = HolidayEngine.get_holidays(2026, "US")
        self.assertIn(date(2026, 1, 1), hols)
        self.assertIn(date(2026, 7, 4), hols)
        # Thanksgiving 2026 : 4e jeudi de novembre = 26 novembre 2026
        self.assertIn(date(2026, 11, 26), hols)

    def test_uk_holidays_2026(self):
        hols = HolidayEngine.get_holidays(2026, "GB")
        self.assertIn(date(2026, 1, 1), hols)
        self.assertIn(date(2026, 12, 25), hols)
        self.assertIn(date(2026, 12, 26), hols)

    def test_italy_holidays_2026(self):
        hols = HolidayEngine.get_holidays(2026, "IT")
        self.assertIn(date(2026, 4, 25), hols)
        self.assertIn(date(2026, 6, 2), hols)

    def test_spain_holidays_2026(self):
        hols = HolidayEngine.get_holidays(2026, "ES")
        self.assertIn(date(2026, 10, 12), hols)
        self.assertIn(date(2026, 12, 6), hols)

    def test_germany_holidays_2026(self):
        hols = HolidayEngine.get_holidays(2026, "DE")
        self.assertIn(date(2026, 10, 3), hols)

    def test_ukraine_holidays_2026(self):
        hols = HolidayEngine.get_holidays(2026, "UA")
        self.assertIn(date(2026, 8, 24), hols)


class TestSolarShading(unittest.TestCase):
    """Vérification des calculs géométriques et solaires."""

    def test_azimuth_resolution(self):
        self.assertEqual(resolve_azimuth("N"), 0.0)
        self.assertEqual(resolve_azimuth("E"), 90.0)
        self.assertEqual(resolve_azimuth("S"), 180.0)
        self.assertEqual(resolve_azimuth("O"), 270.0)
        self.assertEqual(resolve_azimuth("SE"), 135.0)
        self.assertEqual(resolve_azimuth(180), 180.0)

    def test_solar_incidence(self):
        # Plein face
        self.assertEqual(calculate_solar_incidence(180.0, 180.0), 0.0)
        # Écart de 45°
        self.assertEqual(calculate_solar_incidence(180.0, 225.0), 45.0)
        # Écart circulaire (Nord 0° vs Ouest 350°)
        self.assertEqual(calculate_solar_incidence(0.0, 350.0), 10.0)

    def test_is_sun_striking(self):
        # Façade Sud (180°), soleil à 170°, élévation 40° ➔ dans le cône de 60°
        striking, inc = is_sun_striking_window(180.0, 170.0, 40.0, cone_angle=60.0)
        self.assertTrue(striking)
        self.assertEqual(inc, 10.0)

        # Façade Sud (180°), soleil à 270° (Ouest) ➔ écart de 90° > 60° ➔ hors cône
        striking, inc = is_sun_striking_window(180.0, 270.0, 40.0, cone_angle=60.0)
        self.assertFalse(striking)
        self.assertEqual(inc, 90.0)

        # Soleil sous l'horizon (-5°)
        striking, _ = is_sun_striking_window(180.0, 180.0, -5.0)
        self.assertFalse(striking)



from recurrence import RecurrenceEngine


class TestRecurrenceAndDateModes(unittest.TestCase):
    """Vérification des modes de récurrence (Tous les, Prochain, Date)."""

    def test_recurrence_every_matching(self):
        # Dimanche 20 Septembre 2026 à 07:30
        now = datetime(2026, 9, 20, 7, 30)  # weekday 6 = Dimanche
        sched = {
            "recurrence_mode": "every",
            "time": "07:30",
            "weekdays": [5, 6],  # Samedi, Dimanche
        }
        self.assertTrue(RecurrenceEngine.check_trigger_match(sched, now))

        # Test mauvais jour (Lundi 21 Septembre 2026)
        now_monday = datetime(2026, 9, 21, 7, 30)
        self.assertFalse(RecurrenceEngine.check_trigger_match(sched, now_monday))

    def test_recurrence_next_mode(self):
        # Prochain Mardi
        now_sunday = datetime(2026, 9, 20, 10, 0)
        sched = {
            "recurrence_mode": "next",
            "time": "18:00",
            "weekdays": [1],  # Mardi
            "enabled": True,
        }
        # Prochain mardi = 22 Septembre 2026
        next_run = RecurrenceEngine.compute_next_run(sched, now_sunday)
        self.assertIsNotNone(next_run)
        self.assertTrue(next_run.startswith("2026-09-22T18:00:00"))

    def test_recurrence_date_exact_day(self):
        # 25 Décembre 2026 à 08:00
        now_christmas = datetime(2026, 12, 25, 8, 0)
        sched = {
            "recurrence_mode": "date",
            "time": "08:00",
            "month": 12,
            "year": 2026,
            "date_selection_type": "exact_day",
            "day_of_month": 25,
        }
        self.assertTrue(RecurrenceEngine.check_trigger_match(sched, now_christmas))

        # Mauvais jour (24 Décembre)
        now_eve = datetime(2026, 12, 24, 8, 0)
        self.assertFalse(RecurrenceEngine.check_trigger_match(sched, now_eve))

        # Même jour autre année (2027)
        now_2027 = datetime(2027, 12, 25, 8, 0)
        self.assertFalse(RecurrenceEngine.check_trigger_match(sched, now_2027))

    def test_recurrence_date_every_year(self):
        sched = {
            "recurrence_mode": "date",
            "time": "09:00",
            "month": 7,
            "year": "every_year",
            "date_selection_type": "exact_day",
            "day_of_month": 14,
        }
        # 14 Juillet 2026
        self.assertTrue(RecurrenceEngine.check_trigger_match(sched, datetime(2026, 7, 14, 9, 0)))
        # 14 Juillet 2027
        self.assertTrue(RecurrenceEngine.check_trigger_match(sched, datetime(2027, 7, 14, 9, 0)))
        # 15 Juillet 2026
        self.assertFalse(RecurrenceEngine.check_trigger_match(sched, datetime(2026, 7, 15, 9, 0)))

    def test_recurrence_date_weekdays_in_month(self):
        # Tous les Lundis d'Août 2026
        sched = {
            "recurrence_mode": "date",
            "time": "14:00",
            "month": 8,
            "year": 2026,
            "date_selection_type": "weekdays",
            "weekdays": [0],  # Lundi
        }
        # 3 Août 2026 est un Lundi
        self.assertTrue(RecurrenceEngine.check_trigger_match(sched, datetime(2026, 8, 3, 14, 0)))
        # 4 Août 2026 est un Mardi
        self.assertFalse(RecurrenceEngine.check_trigger_match(sched, datetime(2026, 8, 4, 14, 0)))
        # 7 Septembre 2026 est un Lundi mais mois de Septembre
        self.assertFalse(RecurrenceEngine.check_trigger_match(sched, datetime(2026, 9, 7, 14, 0)))


if __name__ == "__main__":
    unittest.main()
