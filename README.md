# <p align="center"><img src="images/icon@2x.png" alt="DomoLink-Planification Logo" width="120"><br>🗓️ DomoLink-Planification</p>

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![version](https://img.shields.io/badge/version-v2.0.2-blue.svg)](https://github.com/SocrateMobile/DomoLink-Planification/releases)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.4+-41BDF5.svg)](https://www.home-assistant.io)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Socrate-FFDD00?logo=buy-me-a-coffee&logoColor=000000)](https://buymeacoffee.com/Socrate)

**DomoLink-Planification** est une intégration Home Assistant haut de gamme conçue pour orchestrer des déclenchements temporels avancés, des déclencheurs de présence géolocalisée (zones), des planifications récurrentes contextuelles, la **gestion bioclimatique solaire ultra-précise des volets roulants**, et le **contrôle universel automatisé de portail & accès**.

[![Buy Me A Coffee](https://img.buymeacoffee.com/button-api/?text=Buy+me+a+coffee&emoji=☕&slug=Socrate&button_colour=FFDD00&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/Socrate)

---

## 🌟 Fonctionnalités Principales

### 1. ☀️ Gestion Bioclimatique Solaire des Volets Roulants
* **Orientation par boussole 16 secteurs** (Nord, Nord-Est, Est, Sud-Est, Sud, Sud-Ouest, Ouest, etc. ou azimut précis de 0° à 359°).
* **Suivi astronomique en temps réel** : Calcul de l'angle d'incidence du soleil sur la vitre d'après l'azimut et l'élévation solaires (`sun.sun`).
* **Confort d'été (Protection Anti-Surchauffe)** :
  * Si la température dépasse le seuil défini (ex: > 24°C) **ET** que le soleil frappe directement la baie vitrée ➔ Le volet se ferme automatiquement à la position d'ombrage configurée (ex: 20%).
  * Dès que le soleil tourne et quitte la façade ➔ Le volet se rouvre automatiquement (ex: 100%) pour faire entrer la lumière naturelle.
* **Hystérésis & Anti-battement** : Temporisation intelligente pour éviter l'usure mécanique des moteurs lors d'éclaircies intermittentes.
* **Autocomplétion intelligente** : Sélecteurs filtrés avec recherche en direct pour les volets (`cover.*`) et capteurs de température (`sensor.*`).

---

### 2. 📍 Déclencheurs de Présence & Zones Géographiques
* **Arrivée dans une zone** (`zone_enter`) : Déclenchement instantané à l'entrée dans une zone.
* **Sortie d'une zone** (`zone_leave`) : Déclenchement instantané lors du départ d'une zone.
* **Filtre par personne** : Ciblage d'une personne spécifique (`person.*`, `device_tracker.*`) ou de toute personne indistinctement.
* **Combinaison temporelle** : Possibilité d'associer un déclencheur de zone à des jours spécifiques de la semaine ou des plages calendaires.

---

### 3. 🔁 Fréquences Flexibles & Dates Précises
* **🔁 Tous les** : Répétition hebdomadaire aux jours choisis.
* **⏩ Prochain** : Exécution unique lors du prochain jour sélectionné, avec option de désactivation ou suppression post-exécution.
* **📅 Date** : Sélection du mois et de l'année (ou répétition annuelle), avec sous-modes au choix :
  * *Jour précis (1 à 31)*
  * *Jours de la semaine dans le mois*

---

### 4. 🏷️ Cibles Universelles, Étiquettes & Rappels Multi-Canaux
* **Étiquettes (Labels HA)**, entités directes, pièces (Areas), scripts, automatisations et scènes.
* **Rappels & Notifications Multi-Canaux** : Envoi de messages personnalisés vers Free Mobile SMS, Telegram, l'application officielle Home Assistant ou notifications persistantes.

---

### 5. 🌍 Calendriers & Jours Fériés Multi-Pays (100% Offline)
Moteur autonome (sans API tierce) pour :
* 🇫🇷 **France (FR)**, 🇺🇸 **États-Unis (US)**, 🇬🇧 **Royaume-Uni (GB)**, 🇮🇹 **Italie (IT)**, 🇪🇸 **Espagne (ES)**, 🇩🇪 **Allemagne (DE)**, 🇺🇦 **Ukraine (UA)**.
* Options : *Actif tous les jours*, *Exclure jours fériés*, *Comportement Week-end*, *Uniquement jours fériés*.

---

### 6. 🎛️ Panneau Latéral Glassmorphism & Badge Bleu France
* **Badge Bleu France** (`#002395`) avec texte blanc contrasté dans le menu latéral gauche de Home Assistant.
* **Bouton « Créer carte Lovelace »** en 1-clic copiant le code YAML de la carte personnalisée `domolink-planification-card`.

---

### 7. 🚪 Portail & Accès Universel (Nouveauté v1.4.0)
* **Fermeture automatique intelligente après oubli** : Compte à rebours dynamique différencié Jour (ex: 10 min) et Nuit (ex: 3 min).
* **Détection d'obstacles et vérification de course** : Contrôle après manœuvre (ex: 60s), envoi d'alertes SMS/notifications en cas de blocage et relances programmées (jusqu'à 6 tentatives).
* **Modes Maintien ouvert** : Boutons 1-clic pour suspendre l'auto-fermeture (15 min, 30 min, 1h, Permanent).
* **Compatibilité universelle** :
  * Relais à contact sec / impulsion (ex: Shelly 1, Shelly Uni) avec durée d'impulsion réglable.
  * Deux contacts séparés (ouverture / fermeture distinctes).
  * Entités Portail natives Home Assistant (`cover.*`).
  * Interrupteurs bistables classiques (ON / OFF).
  * Inversion de polarité du capteur magnétique intégrée.
* **Visuel interactif animé en SVG** : Portail temps réel avec gyrophare, barre de progression et Easter egg sonore 8-bit.

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
---

## ☕ Soutenir le projet / Support

Si vous appréciez cette intégration et souhaitez soutenir son développement continu ainsi que la maintenance des futures versions :

<a href="https://buymeacoffee.com/Socrate" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50" width="210">
</a>

## 📄 Licence
Ce projet est sous licence MIT. Développé par **SocrateMobile** & **Jean-Frédéric Lavigne**.
