"""Calculateur offline des jours fériés pour FR, US, GB, IT, ES, DE et UA."""

from datetime import date, timedelta
from typing import Final

try:
    from .const import (
        COUNTRY_DE,
        COUNTRY_ES,
        COUNTRY_FR,
        COUNTRY_GB,
        COUNTRY_IT,
        COUNTRY_UA,
        COUNTRY_US,
    )
except (ImportError, ValueError):
    from const import (
        COUNTRY_DE,
        COUNTRY_ES,
        COUNTRY_FR,
        COUNTRY_GB,
        COUNTRY_IT,
        COUNTRY_UA,
        COUNTRY_US,
    )


def calculate_easter_gregorian(year: int) -> date:
    """Calcul de la date de Pâques grégorienne (algorithme de Butcher/Meeus)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def calculate_easter_orthodox(year: int) -> date:
    """Calcul de la date de Pâques orthodoxe (julienne convertie en grégorienne)."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    julian_date = date(year, month, day)
    # Décalage grégorien-julien (13 jours pour 1900-2099)
    return julian_date + timedelta(days=13)


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Retourne le n-ième jour de la semaine d'un mois donné (0=Lundi, 6=Dimanche)."""
    first_day = date(year, month, 1)
    day_offset = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=day_offset)
    return first_occurrence + timedelta(weeks=n - 1)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Retourne le dernier jour de la semaine d'un mois donné."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    day_offset = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=day_offset)


class HolidayEngine:
    """Moteur de calcul de jours fériés autonome sans dépendance externe."""

    @classmethod
    def get_holidays(cls, year: int, country: str) -> dict[date, str]:
        """Retourne le dictionnaire {date: nom_du_jour_ferie} pour une année et un pays."""
        country_norm = (country or COUNTRY_FR).upper()
        if country_norm == COUNTRY_FR:
            return cls._get_holidays_france(year)
        if country_norm == COUNTRY_US:
            return cls._get_holidays_usa(year)
        if country_norm == COUNTRY_GB:
            return cls._get_holidays_uk(year)
        if country_norm == COUNTRY_IT:
            return cls._get_holidays_italy(year)
        if country_norm == COUNTRY_ES:
            return cls._get_holidays_spain(year)
        if country_norm == COUNTRY_DE:
            return cls._get_holidays_germany(year)
        if country_norm == COUNTRY_UA:
            return cls._get_holidays_ukraine(year)
        return cls._get_holidays_france(year)

    @classmethod
    def is_holiday(cls, target_date: date, country: str) -> bool:
        """Vérifie si une date précise est un jour férié."""
        holidays = cls.get_holidays(target_date.year, country)
        return target_date in holidays

    @classmethod
    def get_holiday_name(cls, target_date: date, country: str) -> str | None:
        """Retourne le nom du jour férié ou None."""
        holidays = cls.get_holidays(target_date.year, country)
        return holidays.get(target_date)

    # -------------------------------------------------------------------------
    # 🇫🇷 FRANCE
    # -------------------------------------------------------------------------
    @classmethod
    def _get_holidays_france(cls, year: int) -> dict[date, str]:
        easter = calculate_easter_gregorian(year)
        return {
            date(year, 1, 1): "Jour de l'An",
            easter + timedelta(days=1): "Lundi de Pâques",
            date(year, 5, 1): "Fête du Travail",
            date(year, 5, 8): "Victoire 1945",
            easter + timedelta(days=39): "Ascension",
            easter + timedelta(days=50): "Lundi de Pentecôte",
            date(year, 7, 14): "Fête Nationale",
            date(year, 8, 15): "Assomption",
            date(year, 11, 1): "Toussaint",
            date(year, 11, 11): "Armistice 1918",
            date(year, 12, 25): "Noël",
        }

    # -------------------------------------------------------------------------
    # 🇺🇸 ÉTATS-UNIS
    # -------------------------------------------------------------------------
    @classmethod
    def _get_holidays_usa(cls, year: int) -> dict[date, str]:
        holidays = {
            date(year, 1, 1): "New Year's Day",
            _nth_weekday_of_month(year, 1, 0, 3): "Martin Luther King Jr. Day",
            _nth_weekday_of_month(year, 2, 0, 3): "Presidents' Day",
            _last_weekday_of_month(year, 5, 0): "Memorial Day",
            date(year, 6, 19): "Juneteenth",
            date(year, 7, 4): "Independence Day",
            _nth_weekday_of_month(year, 9, 0, 1): "Labor Day",
            _nth_weekday_of_month(year, 10, 0, 2): "Columbus Day",
            date(year, 11, 11): "Veterans Day",
            _nth_weekday_of_month(year, 11, 3, 4): "Thanksgiving",
            date(year, 12, 25): "Christmas Day",
        }
        return holidays

    # -------------------------------------------------------------------------
    # 🇬🇧 ROYAUME-UNI (Bank Holidays)
    # -------------------------------------------------------------------------
    @classmethod
    def _get_holidays_uk(cls, year: int) -> dict[date, str]:
        easter = calculate_easter_gregorian(year)
        holidays = {
            date(year, 1, 1): "New Year's Day",
            easter - timedelta(days=2): "Good Friday",
            easter + timedelta(days=1): "Easter Monday",
            _nth_weekday_of_month(year, 5, 0, 1): "Early May Bank Holiday",
            _last_weekday_of_month(year, 5, 0): "Spring Bank Holiday",
            _last_weekday_of_month(year, 8, 0): "Summer Bank Holiday",
            date(year, 12, 25): "Christmas Day",
            date(year, 12, 26): "Boxing Day",
        }
        return holidays

    # -------------------------------------------------------------------------
    # 🇮🇹 ITALIE
    # -------------------------------------------------------------------------
    @classmethod
    def _get_holidays_italy(cls, year: int) -> dict[date, str]:
        easter = calculate_easter_gregorian(year)
        return {
            date(year, 1, 1): "Capodanno",
            date(year, 1, 6): "Epifania",
            easter + timedelta(days=1): "Lunedì dell'Angelo",
            date(year, 4, 25): "Festa della Liberazione",
            date(year, 5, 1): "Festa dei Lavoratori",
            date(year, 6, 2): "Festa della Repubblica",
            date(year, 8, 15): "Ferragosto",
            date(year, 11, 1): "Tutti i Santi",
            date(year, 12, 8): "Immacolata Concezione",
            date(year, 12, 25): "Natale",
            date(year, 12, 26): "Santo Stefano",
        }

    # -------------------------------------------------------------------------
    # 🇪🇸 ESPAGNE
    # -------------------------------------------------------------------------
    @classmethod
    def _get_holidays_spain(cls, year: int) -> dict[date, str]:
        easter = calculate_easter_gregorian(year)
        return {
            date(year, 1, 1): "Año Nuevo",
            date(year, 1, 6): "Epifanía del Señor",
            easter - timedelta(days=2): "Viernes Santo",
            date(year, 5, 1): "Fiesta del Trabajo",
            date(year, 8, 15): "Asunción de la Virgen",
            date(year, 10, 12): "Fiesta Nacional de España",
            date(year, 11, 1): "Todos los Santos",
            date(year, 12, 6): "Día de la Constitución Española",
            date(year, 12, 8): "Inmaculada Concepción",
            date(year, 12, 25): "Navidad",
        }

    # -------------------------------------------------------------------------
    # 🇩🇪 ALLEMAGNE
    # -------------------------------------------------------------------------
    @classmethod
    def _get_holidays_germany(cls, year: int) -> dict[date, str]:
        easter = calculate_easter_gregorian(year)
        return {
            date(year, 1, 1): "Neujahr",
            easter - timedelta(days=2): "Karfreitag",
            easter + timedelta(days=1): "Ostermontag",
            date(year, 5, 1): "Tag der Arbeit",
            easter + timedelta(days=39): "Christi Himmelfahrt",
            easter + timedelta(days=50): "Pfingstmontag",
            date(year, 10, 3): "Tag der Deutschen Einheit",
            date(year, 12, 25): "1. Weihnachtstag",
            date(year, 12, 26): "2. Weihnachtstag",
        }

    # -------------------------------------------------------------------------
    # 🇺🇦 UKRAINE
    # -------------------------------------------------------------------------
    @classmethod
    def _get_holidays_ukraine(cls, year: int) -> dict[date, str]:
        orthodox_easter = calculate_easter_orthodox(year)
        return {
            date(year, 1, 1): "Новий рік (New Year)",
            date(year, 3, 8): "Міжнародний жіночий день (Women's Day)",
            orthodox_easter + timedelta(days=1): "Великодній понеділок (Easter Monday)",
            date(year, 5, 1): "День праці (Labor Day)",
            date(year, 5, 8): "День пам'яті та перемоги (Victory Day)",
            date(year, 6, 28): "День Конституції України (Constitution Day)",
            date(year, 8, 24): "День Незалежності України (Independence Day)",
            date(year, 10, 1): "День захисників і захисниць України (Defenders Day)",
            date(year, 12, 25): "Різдво Христове (Christmas)",
        }
