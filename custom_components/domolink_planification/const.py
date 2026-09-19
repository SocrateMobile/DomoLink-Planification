"""Constantes pour l'intégration DomoLink-Planification."""

from typing import Final

DOMAIN: Final = "domolink_planification"
NAME: Final = "DomoLink-Planification"
VERSION: Final = "1.0.1"

# Panneau Lovelace & Frontend
PANEL_URL_PATH: Final = "domolink-planification"
PANEL_TITLE: Final = "Planification"
PANEL_ICON: Final = "mdi:calendar-clock"
PANEL_NAME: Final = "domolink_planification-panel"
FRONTEND_URL_PATH: Final = "/domolink_planification_panel"
FRONTEND_FILE_NAME: Final = "domolink_planification-panel.js"

# Options de configuration
CONF_ENABLE_PANEL: Final = "enable_panel"
CONF_DEFAULT_COUNTRY: Final = "default_country"
CONF_DEFAULT_HOLIDAY_MODE: Final = "default_holiday_mode"

# Types de cibles
TARGET_TYPE_ENTITY: Final = "entity"
TARGET_TYPE_LABEL: Final = "label"
TARGET_TYPE_AREA: Final = "area"
TARGET_TYPE_SCRIPT: Final = "script"
TARGET_TYPE_AUTOMATION: Final = "automation"
TARGET_TYPE_SCENE: Final = "scene"
TARGET_TYPE_NOTIFICATION: Final = "notification"
TARGET_TYPE_SEQUENCE: Final = "sequence"

# Types de déclencheurs
TRIGGER_TYPE_TIME: Final = "time"
TRIGGER_TYPE_SOLAR: Final = "solar"
TRIGGER_TYPE_INTERVAL: Final = "interval"
TRIGGER_TYPE_ONCE: Final = "once"
TRIGGER_TYPE_SOLAR_SHADING: Final = "solar_shading"

# Jours fériés & Pays
COUNTRY_FR: Final = "FR"
COUNTRY_US: Final = "US"
COUNTRY_GB: Final = "GB"
COUNTRY_IT: Final = "IT"
COUNTRY_ES: Final = "ES"
COUNTRY_DE: Final = "DE"
COUNTRY_UA: Final = "UA"

COUNTRIES: Final = {
    COUNTRY_FR: "France 🇫🇷",
    COUNTRY_US: "États-Unis 🇺🇸",
    COUNTRY_GB: "Royaume-Uni 🇬🇧",
    COUNTRY_IT: "Italie 🇮🇹",
    COUNTRY_ES: "Espagne 🇪🇸",
    COUNTRY_DE: "Allemagne 🇩🇪",
    COUNTRY_UA: "Ukraine 🇺🇦",
}

# Modes de gestion des jours fériés
HOLIDAY_MODE_ALWAYS: Final = "always"             # Exécuter normalement tous les jours
HOLIDAY_MODE_EXCLUDE: Final = "exclude"           # Ignorer les jours fériés
HOLIDAY_MODE_WEEKEND: Final = "weekend"           # Appliquer le comportement 'Week-end'
HOLIDAY_MODE_ONLY: Final = "only_holidays"        # Uniquement les jours fériés

# Boussole 16 secteurs & Azimuts (0° = Nord, 90° = Est, 180° = Sud, 270° = Ouest)
COMPASS_N: Final = "N"
COMPASS_NNE: Final = "NNE"
COMPASS_NE: Final = "NE"
COMPASS_ENE: Final = "ENE"
COMPASS_E: Final = "E"
COMPASS_ESE: Final = "ESE"
COMPASS_SE: Final = "SE"
COMPASS_SSE: Final = "SSE"
COMPASS_S: Final = "S"
COMPASS_SSO: Final = "SSO"
COMPASS_SO: Final = "SO"
COMPASS_OSO: Final = "OSO"
COMPASS_O: Final = "O"
COMPASS_ONO: Final = "ONO"
COMPASS_NO: Final = "NO"
COMPASS_NNO: Final = "NNO"

COMPASS_AZIMUTH: Final[dict[str, float]] = {
    COMPASS_N: 0.0,
    COMPASS_NNE: 22.5,
    COMPASS_NE: 45.0,
    COMPASS_ENE: 67.5,
    COMPASS_E: 90.0,
    COMPASS_ESE: 112.5,
    COMPASS_SE: 135.0,
    COMPASS_SSE: 157.5,
    COMPASS_S: 180.0,
    COMPASS_SSO: 202.5,
    COMPASS_SO: 225.0,
    COMPASS_OSO: 247.5,
    COMPASS_O: 270.0,
    COMPASS_ONO: 292.5,
    COMPASS_NO: 315.0,
    COMPASS_NNO: 337.5,
}

# Modes de suivi solaire des volets
SHADING_MODE_SUMMER: Final = "summer"  # Protection anti-surchauffe
SHADING_MODE_WINTER: Final = "winter"  # Gain solaire passif

# Stockage
STORAGE_KEY: Final = "domolink_planification_data"
STORAGE_VERSION: Final = 1
