# 🗓️ DomoLink-Planification

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![version](https://img.shields.io/badge/version-v1.0.0-blue.svg)](https://github.com/SocrateMobile/DomoLink-Planification/releases)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.4+-41BDF5.svg)](https://www.home-assistant.io)

**DomoLink-Planification** est une intégration Home Assistant haut de gamme conçue pour orchestrer des déclenchements temporels avancés, des planifications récurrentes contextuelles, et une **gestion bioclimatique solaire ultra-précise des volets roulants**.

---

## 🌟 Fonctionnalités Principales

### 1. ☀️ Gestion Bioclimatique Solaire des Volets Roulants
* **Orientation par boussole 16 secteurs** (Nord, Nord-Est, Est, Sud-Est, Sud, Sud-Ouest, Ouest, etc. ou azimut précis de 0° à 359°).
* **Suivi astronomique en temps réel** : Calcul de l'angle d'incidence du soleil sur la vitre d'après l'azimut et l'élévation solaires (`sun.sun`).
* **Confort d'été (Protection Anti-Surchauffe)** :
  * Si la température dépasse le seuil défini (ex: > 24°C) **ET** que le soleil frappe directement la baie vitrée ➔ Le volet se ferme automatiquement à la position d'ombrage configurée (ex: 20%).
  * Dès que le soleil tourne et quitte la façade ➔ Le volet se rouvre automatiquement (ex: 100%) pour faire entrer la lumière naturelle.
* **Hystérésis & Anti-battement** : Temporisation intelligente pour éviter l'usure mécanique des moteurs lors d'éclaircies intermittentes.

---

### 2. 🏷️ Cibles Universelles & Étiquettes (Labels HA)
Déclenchez vos actions sur n'importe quel élément de Home Assistant :
* **Étiquettes (Labels natifs HA 2024+)** : Ciblez en un mot toutes les entités associées à une étiquette (`label: rez_de_chaussee`, `label: volets`, `label: exterieur`).
* **Entités directes** : `light.salon`, `cover.volet_cuisine`, `climate.cuisine`, `media_player.salon`...
* **Zones / Pièces (Areas)** : Toutes les entités d'une pièce.
* **Scripts, Automatisations & Scènes** : `script.<nom>`, `automation.trigger`, `scene.turn_on`.
* **Notifications** : Notification push sur smartphone, notification persistante HA, ou annonce vocale TTS sur enceintes connectées.
* **Séquenceur multi-étapes** : Enchaînement de plusieurs actions espacées dans le temps.

---

### 3. 🌍 Calendriers & Jours Fériés Multi-Pays (100% Offline)
Moteur de calcul autonome (sans API externe ni dépendance tierce) pour :
* 🇫🇷 **France (FR)** : 11 jours fériés civils et religieux + vacances scolaires.
* 🇺🇸 **États-Unis (US)** : Jours fériés fédéraux (New Year, MLK, Memorial Day, Labor Day, Thanksgiving...).
* 🇬🇧 **Royaume-Uni (GB)** : Bank Holidays anglais et écossais.
* 🇮🇹 **Italie (IT)** : Capodanno, Epifania, Pasquetta, Liberazione, Ferragosto...
* 🇪🇸 **Espagne (ES)** : Año Nuevo, Reyes, Viernes Santo, Fiesta Nacional...
* 🇩🇪 **Allemagne (DE)** : Neujahr, Karfreitag, Ostermontag, Deutsche Einheit...
* 🇺🇦 **Ukraine (UA)** : Nouvel An, Pâques orthodoxe, Constitution, Indépendance...
* **Modes sélectionnables** : *Actif tous les jours*, *Ne pas exécuter les jours fériés*, *Comportement "Week-end" les jours fériés*, *Uniquement les jours fériés*.

---

### 4. 🎛️ Panneau Latéral & Carte Lovelace 1-Clic
* **Panneau latéral dédié** au design Glassmorphism sombre et épuré.
* **Bouton « Créer carte Lovelace »** : Copie instantanément dans le presse-papier le code YAML prêt à l'emploi pour vos tableaux de bord.
* **Activable / Désactivable** en un clic dans les options de l'intégration.

---

## 🚀 Installation

### Via HACS (Recommandé)
1. Ouvrez HACS ➔ **Intégrations** ➔ Cliquez sur les trois petits points en haut à droite ➔ **Dépôts personnalisés**.
2. Ajoutez l'URL : `https://github.com/SocrateMobile/DomoLink-Planification`
3. Catégorie : **Intégration**.
4. Cliquez sur **Télécharger**, puis redémarrez Home Assistant.
5. Allez dans **Paramètres ➔ Appareils et services ➔ Ajouter une intégration ➔ DomoLink-Planification**.

---

## 🛠️ Services Exposés

| Service | Description | Paramètres |
| :--- | :--- | :--- |
| `domolink_planification.trigger_schedule` | Déclenche immédiatement une planification | `schedule_id` (obligatoire) |
| `domolink_planification.refresh_solar_shading` | Force la réévaluation de tous les volets solaires | Aucun |
| `domolink_planification.set_schedule_enabled` | Active ou suspend une règle | `schedule_id`, `enabled` (bool) |

---

## 📄 Licence
Ce projet est sous licence MIT. Développé par **SocrateMobile** & **Jean-Frédéric Lavigne**.
