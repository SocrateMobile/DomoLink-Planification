/**
 * DomoLink-Planification — Panneau Tactile & Carte Lovelace (v1.3.0)
 * Glassmorphism sombre, suivi solaire bioclimatique des volets, gestion multi-pays des jours fériés.
 */

(function () {
  const CARD_NAME = "domolink-planification-card";
  const PANEL_NAME = "domolink_planification-panel";

  const COMPASS_OPTIONS = [
    { label: "Nord (0°)", val: "N", deg: 0 },
    { label: "Nord-Nord-Est (22.5°)", val: "NNE", deg: 22.5 },
    { label: "Nord-Est (45°)", val: "NE", deg: 45 },
    { label: "Est-Nord-Est (67.5°)", val: "ENE", deg: 67.5 },
    { label: "Est (90°)", val: "E", deg: 90 },
    { label: "Est-Sud-Est (112.5°)", val: "ESE", deg: 112.5 },
    { label: "Sud-Est (135°)", val: "SE", deg: 135 },
    { label: "Sud-Sud-Est (157.5°)", val: "SSE", deg: 157.5 },
    { label: "Sud (180°)", val: "S", deg: 180 },
    { label: "Sud-Sud-Ouest (202.5°)", val: "SSO", deg: 202.5 },
    { label: "Sud-Ouest (225°)", val: "SO", deg: 225 },
    { label: "Ouest-Sud-Ouest (247.5°)", val: "OSO", deg: 247.5 },
    { label: "Ouest (270°)", val: "O", deg: 270 },
    { label: "Ouest-Nord-Ouest (292.5°)", val: "ONO", deg: 292.5 },
    { label: "Nord-Ouest (315°)", val: "NO", deg: 315 },
    { label: "Nord-Nord-Ouest (337.5°)", val: "NNO", deg: 337.5 },
  ];

  const COUNTRIES = [
    { code: "FR", name: "France 🇫🇷" },
    { code: "US", name: "États-Unis 🇺🇸" },
    { code: "GB", name: "Royaume-Uni 🇬🇧" },
    { code: "IT", name: "Italie 🇮🇹" },
    { code: "ES", name: "Espagne 🇪🇸" },
    { code: "DE", name: "Allemagne 🇩🇪" },
    { code: "UA", name: "Ukraine 🇺🇦" },
  ];

  const WEEKDAYS_LABELS = [
    { id: 0, label: "Lun" },
    { id: 1, label: "Mar" },
    { id: 2, label: "Mer" },
    { id: 3, label: "Jeu" },
    { id: 4, label: "Ven" },
    { id: 5, label: "Sam" },
    { id: 6, label: "Dim" },
  ];

  const MONTHS_LIST = [
    { val: 1, label: "01 - Janvier" },
    { val: 2, label: "02 - Février" },
    { val: 3, label: "03 - Mars" },
    { val: 4, label: "04 - Avril" },
    { val: 5, label: "05 - Mai" },
    { val: 6, label: "06 - Juin" },
    { val: 7, label: "07 - Juillet" },
    { val: 8, label: "08 - Août" },
    { val: 9, label: "09 - Septembre" },
    { val: 10, label: "10 - Octobre" },
    { val: 11, label: "11 - Novembre" },
    { val: 12, label: "12 - Décembre" },
  ];

  const REMINDER_CHANNELS = [
    { id: "app", label: "📱 Application Mobile (HA Companion / Notify)" },
    { id: "free_mobile", label: "💬 SMS Free Mobile" },
    { id: "telegram", label: "✈️ Telegram" },
    { id: "persistent", label: "🔔 Notification Persistante HA" },
  ];

  const STYLES = `
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #f1f5f9;
      background: #0b0f19;
      min-height: 100vh;
      box-sizing: border-box;
      padding: 24px;
      position: relative;
    }
    * { box-sizing: border-box; }
    
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 24px;
      padding: 20px 24px;
      background: rgba(30, 41, 59, 0.7);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.37);
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .header-icon {
      width: 48px;
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #0ea5e9, #0284c7);
      border-radius: 14px;
      box-shadow: 0 4px 16px rgba(14, 165, 233, 0.4);
      overflow: hidden;
      flex-shrink: 0;
    }
    .header-icon img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .header-icon ha-icon {
      --mdc-icon-size: 28px;
      color: #ffffff;
    }
    .btn ha-icon, .btn-icon ha-icon {
      --mdc-icon-size: 18px;
    }
    .badge ha-icon {
      --mdc-icon-size: 13px;
    }
    .tab ha-icon {
      --mdc-icon-size: 18px;
    }
    .header-title h1 {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
      background: linear-gradient(to right, #ffffff, #94a3b8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .header-title p {
      margin: 4px 0 0 0;
      font-size: 13px;
      color: #94a3b8;
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 18px;
      font-size: 14px;
      font-weight: 600;
      color: #fff;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 10px;
      cursor: pointer;
      transition: all 0.2s ease;
      text-decoration: none;
    }
    .btn:hover {
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.25);
      transform: translateY(-1px);
    }
    .btn-primary {
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      border-color: rgba(59, 130, 246, 0.5);
      box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #60a5fa, #3b82f6);
      box-shadow: 0 6px 18px rgba(37, 99, 235, 0.6);
    }
    .btn-clipboard {
      background: linear-gradient(135deg, #10b981, #059669);
      border-color: rgba(16, 185, 129, 0.5);
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
    }
    .btn-clipboard:hover {
      background: linear-gradient(135deg, #34d399, #10b981);
    }
    
    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 24px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding-bottom: 8px;
      overflow-x: auto;
    }
    .tab {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 600;
      color: #94a3b8;
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    .tab.active {
      color: #fff;
      background: rgba(59, 130, 246, 0.2);
      border: 1px solid rgba(59, 130, 246, 0.4);
    }
    .tab:hover:not(.active) {
      color: #cbd5e1;
      background: rgba(255, 255, 255, 0.05);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 20px;
    }
    .card {
      background: rgba(30, 41, 59, 0.6);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 14px;
      padding: 20px;
      transition: all 0.2s ease;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .card:hover {
      border-color: rgba(59, 130, 246, 0.4);
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 700;
      margin: 0;
      color: #f8fafc;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      border-radius: 20px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-success { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-info { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }
    .badge-warning { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-disabled { background: rgba(148, 163, 184, 0.2); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); }

    .card-details {
      font-size: 13px;
      color: #cbd5e1;
      line-height: 1.6;
      margin-bottom: 16px;
    }
    .card-details span.label {
      color: #64748b;
      font-weight: 600;
    }
    .card-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      padding-top: 14px;
    }
    .btn-icon {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: #cbd5e1;
      width: 36px;
      height: 36px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-icon:hover {
      background: rgba(59, 130, 246, 0.3);
      color: #fff;
      border-color: rgba(59, 130, 246, 0.5);
    }
    .btn-icon.delete:hover {
      background: rgba(239, 68, 68, 0.3);
      border-color: rgba(239, 68, 68, 0.5);
      color: #f87171;
    }

    /* Toggle Switch */
    .switch {
      position: relative;
      display: inline-block;
      width: 44px;
      height: 24px;
    }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider {
      position: absolute;
      cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: rgba(255, 255, 255, 0.15);
      transition: .3s;
      border-radius: 24px;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .slider:before {
      position: absolute;
      content: "";
      height: 18px;
      width: 18px;
      left: 2px;
      bottom: 2px;
      background-color: white;
      transition: .3s;
      border-radius: 50%;
    }
    input:checked + .slider {
      background-color: #3b82f6;
    }
    input:checked + .slider:before {
      transform: translateX(20px);
    }

    /* Modal Backdrop & Dialog */
    .modal-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 999999;
      padding: 20px;
    }
    .modal {
      background: #1e293b;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 16px;
      width: 100%;
      max-width: 640px;
      max-height: 90vh;
      overflow-y: auto;
      padding: 24px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
      position: relative;
      z-index: 1000000;
    }
    .modal h2 {
      margin: 0 0 16px 0;
      font-size: 20px;
      color: #fff;
    }
    .form-group {
      margin-bottom: 16px;
    }
    .form-group label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #94a3b8;
      margin-bottom: 6px;
    }
    .form-control {
      width: 100%;
      padding: 10px 14px;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 8px;
      color: #fff;
      font-size: 14px;
      outline: none;
      transition: border 0.2s;
    }
    .form-control:focus {
      border-color: #3b82f6;
    }
    .weekday-selector {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .day-btn {
      flex: 1;
      min-width: 40px;
      padding: 8px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 6px;
      color: #94a3b8;
      cursor: pointer;
      text-align: center;
      font-size: 12px;
      font-weight: 600;
      user-select: none;
    }
    .day-btn.selected {
      background: #3b82f6;
      color: #fff;
      border-color: #60a5fa;
    }

    /* Segmented Controls & Frequency Buttons */
    .segmented-control {
      display: flex;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 10px;
      padding: 4px;
      gap: 4px;
      margin-bottom: 12px;
    }
    .segmented-btn {
      flex: 1;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 600;
      color: #94a3b8;
      background: transparent;
      border: none;
      border-radius: 7px;
      cursor: pointer;
      text-align: center;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    .segmented-btn:hover:not(.active) {
      color: #f1f5f9;
      background: rgba(255, 255, 255, 0.05);
    }
    .segmented-btn.active {
      color: #fff;
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
    }

    /* Sub Tabs inside Date picker */
    .sub-tabs {
      display: flex;
      gap: 8px;
      margin: 12px 0 10px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 6px;
    }
    .sub-tab-btn {
      background: transparent;
      border: 1px solid transparent;
      color: #94a3b8;
      font-size: 12px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .sub-tab-btn:hover:not(.active) {
      color: #cbd5e1;
      background: rgba(255, 255, 255, 0.04);
    }
    .sub-tab-btn.active {
      color: #60a5fa;
      background: rgba(59, 130, 246, 0.15);
      border-color: rgba(59, 130, 246, 0.35);
    }

    /* Countdown & Info Badges */
    .countdown-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(59, 130, 246, 0.15);
      border: 1px solid rgba(59, 130, 246, 0.35);
      color: #60a5fa;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }
    .info-banner {
      background: rgba(59, 130, 246, 0.08);
      border-left: 3px solid #3b82f6;
      border-radius: 6px;
      padding: 8px 12px;
      font-size: 12px;
      color: #cbd5e1;
      margin-top: 8px;
      line-height: 1.4;
    }

    /* Autocomplete Dropdown Component */
    .ac-wrapper {
      position: relative;
      width: 100%;
    }
    .ac-input-group {
      position: relative;
      display: flex;
      align-items: center;
      width: 100%;
    }
    .ac-input-group .form-control {
      padding-right: 64px;
    }
    .ac-controls {
      position: absolute;
      right: 8px;
      display: flex;
      align-items: center;
      gap: 2px;
      height: 100%;
    }
    .ac-btn {
      background: transparent;
      border: none;
      color: #94a3b8;
      cursor: pointer;
      padding: 4px 6px;
      font-size: 11px;
      border-radius: 4px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }
    .ac-btn:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
    }
    .ac-dropdown {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      right: 0;
      max-height: 250px;
      overflow-y: auto;
      background: #0f172a;
      border: 1px solid rgba(59, 130, 246, 0.5);
      border-radius: 10px;
      box-shadow: 0 16px 36px rgba(0, 0, 0, 0.85);
      z-index: 1000020;
      display: none;
      scrollbar-width: thin;
      scrollbar-color: rgba(59, 130, 246, 0.5) transparent;
    }
    .ac-dropdown::-webkit-scrollbar {
      width: 6px;
    }
    .ac-dropdown::-webkit-scrollbar-thumb {
      background: rgba(59, 130, 246, 0.5);
      border-radius: 4px;
    }
    .ac-dropdown.open {
      display: block;
    }
    .ac-item {
      padding: 10px 14px;
      cursor: pointer;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      transition: background 0.15s ease;
    }
    .ac-item:last-child {
      border-bottom: none;
    }
    .ac-item:hover, .ac-item.active {
      background: rgba(59, 130, 246, 0.25);
    }
    .ac-item-content {
      display: flex;
      flex-direction: column;
      gap: 2px;
      overflow: hidden;
      flex: 1;
    }
    .ac-item-name {
      font-size: 13px;
      font-weight: 600;
      color: #f8fafc;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .ac-item-id {
      font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      color: #60a5fa;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .ac-item-badge {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.08);
      color: #cbd5e1;
      white-space: nowrap;
    }
    .ac-item-match {
      color: #38bdf8;
      font-weight: 700;
      text-decoration: underline;
    }
    .ac-empty-msg {
      padding: 16px;
      text-align: center;
      color: #94a3b8;
      font-size: 13px;
      font-style: italic;
    }
    .ac-count-badge {
      display: inline-block;
      font-size: 10px;
      font-weight: 600;
      padding: 1px 8px;
      border-radius: 10px;
      background: rgba(59, 130, 246, 0.2);
      color: #60a5fa;
      margin-left: 8px;
      border: 1px solid rgba(59, 130, 246, 0.3);
    }
    .ac-selection-hint {
      margin-top: 6px;
      font-size: 12px;
      color: #94a3b8;
      padding: 4px 8px;
      background: rgba(255, 255, 255, 0.04);
      border-radius: 6px;
      border-left: 3px solid #3b82f6;
    }
    .ac-selection-hint strong {
      color: #f1f5f9;
    }

    /* Toast */
    .toast {
      position: fixed;
      bottom: 30px;
      right: 30px;
      background: rgba(16, 185, 129, 0.95);
      color: #fff;
      padding: 14px 24px;
      border-radius: 12px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
      font-weight: 600;
      font-size: 14px;
      z-index: 1000005;
      display: flex;
      align-items: center;
      gap: 10px;
      transform: translateY(100px);
      opacity: 0;
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      pointer-events: none;
    }
    .toast.show {
      transform: translateY(0);
      opacity: 1;
      pointer-events: auto;
    }

    /* Solar compass view */
    .compass-box {
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      justify-content: space-around;
      flex-wrap: wrap;
      gap: 20px;
    }
    .sun-data {
      display: flex;
      gap: 24px;
    }
    .sun-metric {
      text-align: center;
    }
    .sun-metric .val {
      font-size: 24px;
      font-weight: 700;
      color: #fbbf24;
    }
    .sun-metric .lbl {
      font-size: 12px;
      color: #94a3b8;
      margin-top: 4px;
    }
  `;

  class DomolinkPlanificationPanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._data = { schedules: {}, history: [], settings: {}, next_runs: {}, solar_states: {} };
      this._activeTab = "schedules";
      this._editingSchedule = null;
    }

    set hass(hass) {
      const oldHass = this._hass;
      this._hass = hass;
      if (!oldHass) {
        this._fetchData();
      }
    }

    connectedCallback() {
      if (typeof applySidebarBadge === "function") {
        applySidebarBadge();
      }
    }

    async _fetchData() {
      if (!this._hass) return;
      try {
        const res = await this._hass.fetchWithAuth("/api/domolink_planification/data");
        if (res.ok) {
          this._data = await res.json();
          this._render();
        }
      } catch (err) {
        console.error("Erreur chargement données DomoLink-Planification:", err);
      }
    }

    _showToast(msg) {
      const toast = this.shadowRoot.querySelector("#toast");
      if (toast) {
        toast.textContent = msg;
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), 3500);
      }
    }

    _copyLovelaceCardCode() {
      const yamlCode = `type: custom:domolink-planification-card\ntitle: "Planifications & Volets"\n`;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(yamlCode).then(() => {
          this._showToast("📋 Code Lovelace copié dans le presse-papier !");
        }).catch(() => {
          this._showToast("Erreur copie presse-papier");
        });
      }
    }

    async _toggleSchedule(schedId, currentStatus) {
      if (!this._hass) return;
      const sched = this._data.schedules[schedId];
      if (sched) {
        sched.enabled = !currentStatus;
        await this._hass.fetchWithAuth("/api/domolink_planification/save_schedule", {
          method: "POST",
          body: JSON.stringify(sched),
        });
        await this._fetchData();
      }
    }

    async _triggerNow(schedId) {
      if (!this._hass) return;
      await this._hass.fetchWithAuth("/api/domolink_planification/trigger_now", {
        method: "POST",
        body: JSON.stringify({ id: schedId }),
      });
      this._showToast("▶️ Action déclenchée immédiatement !");
      await this._fetchData();
    }

    async _deleteSchedule(schedId) {
      if (!confirm("Voulez-vous vraiment supprimer cette planification ?")) return;
      if (!this._hass) return;
      await this._hass.fetchWithAuth("/api/domolink_planification/delete_schedule", {
        method: "POST",
        body: JSON.stringify({ id: schedId }),
      });
      this._showToast("🗑️ Planification supprimée.");
      await this._fetchData();
    }

    _formatCountdown(isoString) {
      if (!isoString || !isoString.includes("T")) return null;
      try {
        const targetTime = new Date(isoString).getTime();
        const diffMs = targetTime - Date.now();
        if (diffMs <= 0) return "Imminent";
        const totalMinutes = Math.floor(diffMs / 60000);
        const totalHours = Math.floor(totalMinutes / 60);
        const days = Math.floor(totalHours / 24);
        const remHours = totalHours % 24;
        const remMinutes = totalMinutes % 60;
        if (days > 0) return `dans ${days}j ${remHours}h`;
        if (totalHours > 0) return `dans ${totalHours}h ${remMinutes}m`;
        return `dans ${remMinutes}m`;
      } catch (e) {
        return null;
      }
    }

    _openScheduleModal(sched = null, isSolar = false) {
      const now = new Date();
      const defaultSched = {
        id: "",
        name: isSolar ? "Volet Salon - Suivi Solaire" : "Nouvelle Planification",
        enabled: true,
        trigger_type: isSolar ? "solar_shading" : "time",
        time_type: "fixed",
        time: "07:30",
        solar_offset_minutes: 0,
        recurrence_mode: "every",
        date_selection_type: "exact_day",
        month: now.getMonth() + 1,
        year: now.getFullYear(),
        day_of_month: now.getDate(),
        weekdays: [0, 1, 2, 3, 4],
        post_execution_action: "disable",
        target_type: isSolar ? "entity" : "label",
        target_value: "",
        action_service: "turn_on",
        reminder_channel: "app",
        reminder_message: "",
        cover_entity_id: "",
        orientation: "S",
        temperature_sensor_id: "",
        temperature_threshold: 24.0,
        shading_position: 20,
        open_position: 100,
        holiday_mode: "always",
        zone_person_id: "any",
        zone_id: "zone.home",
      };
      this._editingSchedule = sched ? Object.assign(defaultSched, JSON.parse(JSON.stringify(sched))) : defaultSched;
      this._renderModal();
    }

    _closeModal() {
      this._editingSchedule = null;
      const modal = this.shadowRoot.querySelector(".modal-backdrop");
      if (modal) modal.remove();
    }

    async _saveScheduleFromModal() {
      if (!this._editingSchedule) return;
      await this._hass.fetchWithAuth("/api/domolink_planification/save_schedule", {
        method: "POST",
        body: JSON.stringify(this._editingSchedule),
      });
      this._closeModal();
      this._showToast("✅ Planification enregistrée avec succès !");
      await this._fetchData();
    }

    _render() {
      const sunState = this._hass ? this._hass.states["sun.sun"] : null;
      const sunAzimuth = sunState ? Math.round(sunState.attributes.azimuth || 0) : "N/A";
      const sunElevation = sunState ? Math.round(sunState.attributes.elevation || 0) : "N/A";

      const schedulesList = Object.values(this._data.schedules || {});
      const timeSchedules = schedulesList.filter(s => s.trigger_type !== "solar_shading");
      const solarSchedules = schedulesList.filter(s => s.trigger_type === "solar_shading");

      this.shadowRoot.innerHTML = `
        <style>${STYLES}</style>
        
        <div class="header">
          <div class="header-left">
            <div class="header-icon">
              <img src="/domolink_planification_panel/icon.png" alt="DomoLink Logo" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
              <ha-icon icon="mdi:calendar-clock" style="display:none;"></ha-icon>
            </div>
            <div class="header-title">
              <h1>DomoLink-Planification</h1>
              <p>Moteur d'automatisation temporelle & gestion bioclimatique des volets</p>
            </div>
          </div>
          <div class="header-actions">
            <button class="btn btn-clipboard" id="btn-copy-card"><ha-icon icon="mdi:content-copy"></ha-icon> <span>Carte Lovelace</span></button>
            <button class="btn btn-primary" id="btn-add-schedule"><ha-icon icon="mdi:plus-circle-outline"></ha-icon> <span>Planification</span></button>
            <button class="btn btn-primary" id="btn-add-solar"><ha-icon icon="mdi:weather-sunny-alert"></ha-icon> <span>Volet Solaire</span></button>
          </div>
        </div>

        <div class="tabs">
          <div class="tab ${this._activeTab === 'schedules' ? 'active' : ''}" data-tab="schedules">
            <ha-icon icon="mdi:calendar-clock"></ha-icon>
            <span>Planifications (${timeSchedules.length})</span>
          </div>
          <div class="tab ${this._activeTab === 'solar' ? 'active' : ''}" data-tab="solar">
            <ha-icon icon="mdi:weather-sunny"></ha-icon>
            <span>Volets Solaires (${solarSchedules.length})</span>
          </div>
          <div class="tab ${this._activeTab === 'history' ? 'active' : ''}" data-tab="history">
            <ha-icon icon="mdi:history"></ha-icon>
            <span>Historique Audit</span>
          </div>
          <div class="tab ${this._activeTab === 'settings' ? 'active' : ''}" data-tab="settings">
            <ha-icon icon="mdi:cog-outline"></ha-icon>
            <span>Paramètres</span>
          </div>
        </div>

        <div id="tab-content">
          ${this._renderActiveTabContent(timeSchedules, solarSchedules, sunAzimuth, sunElevation)}
        </div>

        <div class="toast" id="toast"></div>
      `;

      // Event Listeners sur les boutons du bandeau supérieur
      const btnCopy = this.shadowRoot.querySelector("#btn-copy-card");
      if (btnCopy) btnCopy.addEventListener("click", () => this._copyLovelaceCardCode());

      const btnAddSched = this.shadowRoot.querySelector("#btn-add-schedule");
      if (btnAddSched) btnAddSched.addEventListener("click", () => this._openScheduleModal(null, false));

      const btnAddSolar = this.shadowRoot.querySelector("#btn-add-solar");
      if (btnAddSolar) btnAddSolar.addEventListener("click", () => this._openScheduleModal(null, true));

      // Event Listeners sur les onglets
      this.shadowRoot.querySelectorAll(".tab").forEach(el => {
        el.addEventListener("click", (e) => {
          this._activeTab = e.currentTarget.dataset.tab;
          this._render();
        });
      });

      // Délégation d'événements globale sur le shadowRoot pour garantir que tous les boutons fonctionnent
      this._attachEventDelegation();
    }

    _attachEventDelegation() {
      // 1. Boutons "+ Créer une première règle" sur les états vides
      const emptyAddBtn = this.shadowRoot.querySelector("#btn-empty-add");
      if (emptyAddBtn) {
        emptyAddBtn.addEventListener("click", () => this._openScheduleModal(null, false));
      }

      const solarEmptyAddBtn = this.shadowRoot.querySelector("#btn-solar-empty-add");
      if (solarEmptyAddBtn) {
        solarEmptyAddBtn.addEventListener("click", () => this._openScheduleModal(null, true));
      }

      // 2. Toggles switch sur les cartes
      this.shadowRoot.querySelectorAll(".toggle-schedule").forEach(toggle => {
        toggle.addEventListener("change", (e) => {
          const card = e.currentTarget.closest(".card");
          if (card) {
            const schedId = card.dataset.id;
            this._toggleSchedule(schedId, !e.currentTarget.checked);
          }
        });
      });

      // 3. Boutons d'action sur les cartes
      this.shadowRoot.querySelectorAll(".trigger-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const card = e.currentTarget.closest(".card");
          if (card) this._triggerNow(card.dataset.id);
        });
      });

      this.shadowRoot.querySelectorAll(".edit-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const card = e.currentTarget.closest(".card");
          if (card) {
            const sched = this._data.schedules[card.dataset.id];
            if (sched) this._openScheduleModal(sched, sched.trigger_type === "solar_shading");
          }
        });
      });

      this.shadowRoot.querySelectorAll(".delete-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const card = e.currentTarget.closest(".card");
          if (card) this._deleteSchedule(card.dataset.id);
        });
      });

      // 4. Enregistrement des paramètres
      const btnSaveSettings = this.shadowRoot.querySelector("#btn-save-settings");
      if (btnSaveSettings) {
        btnSaveSettings.addEventListener("click", async () => {
          const country = this.shadowRoot.querySelector("#settings-country").value;
          await this._hass.fetchWithAuth("/api/domolink_planification/save_settings", {
            method: "POST",
            body: JSON.stringify({ country }),
          });
          this._showToast("⚙️ Paramètres enregistrés !");
          await this._fetchData();
        });
      }
    }

    _renderActiveTabContent(timeSchedules, solarSchedules, sunAzimuth, sunElevation) {
      if (this._activeTab === "schedules") {
        if (timeSchedules.length === 0) {
          return `
            <div style="text-align: center; padding: 60px 24px; background: rgba(30,41,59,0.4); border-radius: 16px; border: 1px dashed rgba(255,255,255,0.15);">
              <div class="header-icon" style="margin: 0 auto 16px auto; width: 64px; height: 64px;">
                <ha-icon icon="mdi:calendar-clock" style="--mdc-icon-size:36px; color:#fff;"></ha-icon>
              </div>
              <p style="font-size: 18px; color: #f1f5f9; font-weight: 600; margin: 0 0 8px 0;">Aucune planification temporelle active.</p>
              <p style="font-size: 13px; color: #94a3b8; margin: 0 0 20px 0;">Créez votre première règle pour déclencher des actions, scripts ou étiquettes.</p>
              <button class="btn btn-primary" id="btn-empty-add" style="font-size: 15px; padding: 12px 24px;"><ha-icon icon="mdi:plus-circle-outline"></ha-icon> <span>Créer une première règle</span></button>
            </div>
          `;
        }
        return `
          <div class="grid">
            ${timeSchedules.map(sched => this._renderScheduleCard(sched)).join("")}
          </div>
        `;
      }

      if (this._activeTab === "solar") {
        return `
          <div class="compass-box">
            <div>
              <h3 style="margin:0 0 6px 0; color:#fff;">Trajectoire Solaire en Temps Réel</h3>
              <p style="margin:0; font-size:13px; color:#94a3b8;">Suivi astronomique précis pour le positionnement automatique des baies vitrées</p>
            </div>
            <div class="sun-data">
              <div class="sun-metric">
                <div class="val">${sunAzimuth}°</div>
                <div class="lbl">Azimut Solaire</div>
              </div>
              <div class="sun-metric">
                <div class="val">${sunElevation}°</div>
                <div class="lbl">Élévation Solaire</div>
              </div>
            </div>
          </div>

          <div class="grid">
            ${solarSchedules.length === 0 ? `
              <div style="grid-column: 1/-1; text-align: center; padding: 60px 24px; background: rgba(30,41,59,0.4); border-radius: 16px; border: 1px dashed rgba(255,255,255,0.15);">
                <div class="header-icon" style="margin: 0 auto 16px auto; width: 64px; height: 64px; background: linear-gradient(135deg, #f59e0b, #d97706);">
                  <ha-icon icon="mdi:weather-sunny" style="--mdc-icon-size:36px; color:#fff;"></ha-icon>
                </div>
                <p style="font-size: 18px; color: #f1f5f9; font-weight: 600; margin: 0 0 8px 0;">Aucun volet configuré pour le suivi solaire.</p>
                <p style="font-size: 13px; color: #94a3b8; margin: 0 0 20px 0;">Associez l'orientation de vos façades à la trajectoire solaire pour un confort d'été optimal.</p>
                <button class="btn btn-primary" id="btn-solar-empty-add" style="font-size: 15px; padding: 12px 24px;"><ha-icon icon="mdi:plus-circle-outline"></ha-icon> <span>Configurer un volet solaire</span></button>
              </div>
            ` : solarSchedules.map(sched => this._renderSolarCard(sched)).join("")}
          </div>
        `;
      }

      if (this._activeTab === "history") {
        const history = this._data.history || [];
        return `
          <div style="background: rgba(30, 41, 59, 0.6); border-radius: 14px; border: 1px solid rgba(255,255,255,0.08); overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
              <thead>
                <tr style="background: rgba(15, 23, 42, 0.6); color: #64748b; text-transform: uppercase; font-size: 11px;">
                  <th style="padding: 14px 20px;">Horodatage</th>
                  <th style="padding: 14px 20px;">Règle</th>
                  <th style="padding: 14px 20px;">Statut</th>
                  <th style="padding: 14px 20px;">Détails</th>
                </tr>
              </thead>
              <tbody>
                ${history.length === 0 ? `<tr><td colspan="4" style="padding: 24px; text-align: center; color: #64748b;">Aucun historique récent</td></tr>` : 
                  history.map(item => `
                    <tr style="border-top: 1px solid rgba(255,255,255,0.05);">
                      <td style="padding: 12px 20px; color: #94a3b8;">${new Date(item.timestamp).toLocaleString()}</td>
                      <td style="padding: 12px 20px; font-weight: 600; color: #f8fafc;">${item.name}</td>
                      <td style="padding: 12px 20px;">
                        <span class="badge ${item.status === 'SUCCESS' ? 'badge-success' : (item.status === 'SKIPPED' ? 'badge-warning' : 'badge-info')}">
                          <ha-icon icon="${item.status === 'SUCCESS' ? 'mdi:check-circle-outline' : (item.status === 'SKIPPED' ? 'mdi:skip-next-circle-outline' : 'mdi:information-outline')}"></ha-icon>
                          <span>${item.status}</span>
                        </span>
                      </td>
                      <td style="padding: 12px 20px; color: #cbd5e1;">${item.details || '-'}</td>
                    </tr>
                  `).join("")}
              </tbody>
            </table>
          </div>
        `;
      }

      if (this._activeTab === "settings") {
        const currentCountry = (this._data.settings || {}).country || "FR";
        return `
          <div style="max-width: 600px; background: rgba(30, 41, 59, 0.6); border-radius: 14px; border: 1px solid rgba(255,255,255,0.08); padding: 24px;">
            <h3 style="margin-top:0;">Paramètres de DomoLink-Planification</h3>
            <div class="form-group">
              <label>Pays pour le calcul des Jours Fériés</label>
              <select class="form-control" id="settings-country">
                ${COUNTRIES.map(c => `<option value="${c.code}" ${c.code === currentCountry ? 'selected' : ''}>${c.name}</option>`).join("")}
              </select>
            </div>
            <button class="btn btn-primary" id="btn-save-settings"><ha-icon icon="mdi:content-save-outline"></ha-icon> <span>Enregistrer les paramètres</span></button>
          </div>
        `;
      }
      return "";
    }

    _renderScheduleCard(sched) {
      const isEnabled = sched.enabled !== false;
      const isCompleted = sched.is_completed === true;
      const nextRun = (this._data.next_runs || {})[sched.id] || "Calcul en cours...";
      const nextRunFormatted = nextRun.includes("T") ? new Date(nextRun).toLocaleString() : nextRun;
      const countdown = this._formatCountdown(nextRun);

      // Déclencheur textuel
      let triggerDesc = "";
      if (sched.time_type === "sunrise") {
        const off = sched.solar_offset_minutes || 0;
        triggerDesc = `<span style="display:inline-flex;align-items:center;gap:4px;"><ha-icon icon="mdi:weather-sunset-up" style="--mdc-icon-size:15px;color:#f59e0b;"></ha-icon> Lever du soleil (${off >= 0 ? "+" : ""}${off} min)</span>`;
      } else if (sched.time_type === "sunset") {
        const off = sched.solar_offset_minutes || 0;
        triggerDesc = `<span style="display:inline-flex;align-items:center;gap:4px;"><ha-icon icon="mdi:weather-sunset-down" style="--mdc-icon-size:15px;color:#f97316;"></ha-icon> Coucher du soleil (${off >= 0 ? "+" : ""}${off} min)</span>`;
      } else if (sched.time_type === "zone_enter" || sched.time_type === "zone_leave") {
        const states = (this._hass && this._hass.states) ? this._hass.states : {};
        const isEnter = sched.time_type === "zone_enter";
        const pId = sched.zone_person_id || "any";
        const pName = (pId === "any" || !pId) ? "Toute personne" : (states[pId]?.attributes?.friendly_name || pId);
        const zId = sched.zone_id || "zone.home";
        const rawZone = zId.replace("zone.", "");
        const zName = states[zId]?.attributes?.friendly_name || (rawZone.charAt(0).toUpperCase() + rawZone.slice(1));
        triggerDesc = isEnter
          ? `<span style="display:inline-flex;align-items:center;gap:4px;"><ha-icon icon="mdi:map-marker-radius" style="--mdc-icon-size:15px;color:#10b981;"></ha-icon> Arrivée de <strong>${pName}</strong> dans <strong>${zName}</strong></span>`
          : `<span style="display:inline-flex;align-items:center;gap:4px;"><ha-icon icon="mdi:map-marker-minus" style="--mdc-icon-size:15px;color:#ef4444;"></ha-icon> Sortie de <strong>${pName}</strong> de <strong>${zName}</strong></span>`;
      } else {
        triggerDesc = `<span style="display:inline-flex;align-items:center;gap:4px;"><ha-icon icon="mdi:clock-outline" style="--mdc-icon-size:15px;color:#38bdf8;"></ha-icon> Heure fixe (${sched.time || "07:30"})</span>`;
      }

      // Badge de Fréquence / Périodicité
      let recurrenceBadge = "";
      const rec = sched.recurrence_mode || "every";
      if (rec === "every") {
        const days = (sched.weekdays || []).map(d => (WEEKDAYS_LABELS.find(w => w.id === d) || {}).label || d).join(", ") || "Tous les jours";
        recurrenceBadge = `<span class="badge badge-info"><ha-icon icon="mdi:repeat"></ha-icon> <span>Tous les : ${days}</span></span>`;
      } else if (rec === "next") {
        const days = (sched.weekdays || []).map(d => (WEEKDAYS_LABELS.find(w => w.id === d) || {}).label || d).join(", ") || "Prochain jour";
        recurrenceBadge = `<span class="badge badge-warning"><ha-icon icon="mdi:fast-forward"></ha-icon> <span>Prochain : ${days}</span></span>`;
      } else if (rec === "date") {
        const mLabel = (MONTHS_LIST.find(m => m.val === parseInt(sched.month, 10)) || {}).label || `Mois ${sched.month}`;
        const yLabel = sched.year === "every_year" ? "Chaque année" : sched.year;
        if (sched.date_selection_type === "weekdays") {
          const days = (sched.weekdays || []).map(d => (WEEKDAYS_LABELS.find(w => w.id === d) || {}).label || d).join(", ");
          recurrenceBadge = `<span class="badge badge-info"><ha-icon icon="mdi:calendar-month-outline"></ha-icon> <span>${mLabel} (${yLabel}) [${days}]</span></span>`;
        } else {
          recurrenceBadge = `<span class="badge badge-info"><ha-icon icon="mdi:calendar-month-outline"></ha-icon> <span>Le ${sched.day_of_month || 1} ${mLabel} (${yLabel})</span></span>`;
        }
      }

      // Cible ou Rappel
      let targetDesc = "";
      if (sched.target_type === "reminder") {
        const ch = (REMINDER_CHANNELS.find(c => c.id === sched.reminder_channel) || {}).label || sched.reminder_channel || "Notification";
        targetDesc = `<span style="display:inline-flex;align-items:center;gap:4px;"><ha-icon icon="mdi:bell-ring-outline" style="--mdc-icon-size:15px;color:#a855f7;"></ha-icon> <strong>Rappel [${ch}]</strong> : <span style="color:#e2e8f0;">"${sched.reminder_message || ''}"</span></span>`;
      } else {
        targetDesc = `<span style="display:inline-flex;align-items:center;gap:4px;"><ha-icon icon="mdi:lightning-bolt-outline" style="--mdc-icon-size:15px;color:#38bdf8;"></ha-icon> ${sched.target_type} ➔ <code>${sched.target_value}</code> (${sched.action_service || 'turn_on'})</span>`;
      }

      return `
        <div class="card" data-id="${sched.id}" style="${isCompleted ? 'opacity: 0.65;' : ''}">
          <div>
            <div class="card-header">
              <div>
                <h3 class="card-title">${sched.name}</h3>
                <div style="margin-top: 6px; display:flex; gap:6px; flex-wrap:wrap;">
                  ${recurrenceBadge}
                  ${isCompleted ? '<span class="badge badge-disabled">Terminé</span>' : ''}
                </div>
              </div>
              <label class="switch">
                <input type="checkbox" class="toggle-schedule" ${isEnabled && !isCompleted ? "checked" : ""} ${isCompleted ? "disabled" : ""}>
                <span class="slider"></span>
              </label>
            </div>
            <div class="card-details">
              <div><span class="label">Déclencheur :</span> ${triggerDesc}</div>
              <div><span class="label">Action / Cible :</span> ${targetDesc}</div>
              <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:2px;">
                <span class="label">Prochaine :</span>
                <strong style="color:#60a5fa;">${isCompleted ? 'Exécution unique terminée' : nextRunFormatted}</strong>
                ${!isCompleted && countdown ? `<span class="countdown-badge"><ha-icon icon="mdi:timer-sand"></ha-icon> ${countdown}</span>` : ''}
              </div>
              <div><span class="label">Jours Fériés :</span> ${sched.holiday_mode || 'Actif'}</div>
            </div>
          </div>
          <div class="card-actions">
            <button class="btn-icon trigger-btn" title="Tester maintenant"><ha-icon icon="mdi:play"></ha-icon></button>
            <button class="btn-icon edit-btn" title="Modifier"><ha-icon icon="mdi:pencil-outline"></ha-icon></button>
            <button class="btn-icon delete delete-btn" title="Supprimer"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>
          </div>
        </div>
      `;
    }

    _renderSolarCard(sched) {
      const isEnabled = sched.enabled !== false;
      const state = (this._data.solar_states || {})[sched.id] || {};
      const statusBadge = state.should_shade ? 
        `<span class="badge badge-warning"><ha-icon icon="mdi:weather-sunny"></ha-icon> <span>Fermé Solaire (${sched.shading_position}%)</span></span>` :
        `<span class="badge badge-success"><ha-icon icon="mdi:weather-partly-cloudy"></ha-icon> <span>Ouvert (${sched.open_position}%)</span></span>`;

      return `
        <div class="card" data-id="${sched.id}">
          <div>
            <div class="card-header">
              <div>
                <h3 class="card-title">${sched.name}</h3>
                <div style="margin-top: 6px;">${statusBadge}</div>
              </div>
              <label class="switch">
                <input type="checkbox" class="toggle-schedule" ${isEnabled ? "checked" : ""}>
                <span class="slider"></span>
              </label>
            </div>
            <div class="card-details">
              <div><span class="label">Volet :</span> <code>${sched.cover_entity_id}</code></div>
              <div><span class="label">Exposition Façade :</span> <strong>${sched.orientation} (${state.facade_azimuth || '-'}°)</strong></div>
              <div><span class="label">Incidence Solaire :</span> ${state.incidence_angle !== undefined ? `${state.incidence_angle}°` : '-'}</div>
              <div><span class="label">Seuil Température :</span> ${sched.temperature_threshold}°C (Actuel: ${state.current_temp !== null && state.current_temp !== undefined ? `${state.current_temp}°C` : 'N/A'})</div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 6px;">${state.reason || ''}</div>
            </div>
          </div>
          <div class="card-actions">
            <button class="btn-icon trigger-btn" title="Réévaluer"><ha-icon icon="mdi:refresh"></ha-icon></button>
            <button class="btn-icon edit-btn" title="Modifier"><ha-icon icon="mdi:pencil-outline"></ha-icon></button>
            <button class="btn-icon delete delete-btn" title="Supprimer"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>
          </div>
        </div>
      `;
    }

    _setupEntityAutocomplete(container, {
      inputId,
      dropdownId,
      hintId,
      entities,
      fallbackEntities = null,
      onSelect = null
    }) {
      const input = container.querySelector(`#${inputId}`);
      const dropdown = container.querySelector(`#${dropdownId}`);
      const hint = hintId ? container.querySelector(`#${hintId}`) : null;
      if (!input || !dropdown) return;

      let activeIndex = -1;
      let currentList = [];

      const normalize = (str) => {
        return (str || "")
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .toLowerCase();
      };

      const escapeHtml = (str) => {
        return (str || "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
      };

      const highlightMatches = (text, query) => {
        if (!query) return escapeHtml(text);
        const nText = normalize(text);
        const nQuery = normalize(query);
        const idx = nText.indexOf(nQuery);
        if (idx === -1) return escapeHtml(text);
        const before = escapeHtml(text.substring(0, idx));
        const match = escapeHtml(text.substring(idx, idx + query.length));
        const after = escapeHtml(text.substring(idx + query.length));
        return `${before}<span class="ac-item-match">${match}</span>${after}`;
      };

      const updateHint = (entityId) => {
        if (!hint) return;
        if (!entityId) {
          hint.style.display = "none";
          hint.innerHTML = "";
          return;
        }
        const stateObj = this._hass && this._hass.states ? this._hass.states[entityId] : null;
        if (stateObj) {
          const fn = stateObj.attributes?.friendly_name || entityId;
          const u = stateObj.attributes?.unit_of_measurement || "";
          const val = stateObj.state;
          hint.style.display = "block";
          hint.innerHTML = `Sélectionné : <strong>${escapeHtml(fn)}</strong> (${escapeHtml(val)}${u ? ' ' + escapeHtml(u) : ''})`;
        } else {
          hint.style.display = "block";
          hint.innerHTML = `Entité saisie : <strong>${escapeHtml(entityId)}</strong>`;
        }
      };

      const filterList = (query) => {
        const q = normalize(query.trim());
        if (!q) return entities;

        let filtered = entities.filter(e => {
          return normalize(e.name).includes(q) || normalize(e.id).includes(q);
        });

        if (filtered.length === 0 && fallbackEntities && fallbackEntities.length > 0) {
          filtered = fallbackEntities.filter(e => {
            return normalize(e.name).includes(q) || normalize(e.id).includes(q);
          });
        }
        return filtered;
      };

      const renderDropdown = (items, query = "") => {
        currentList = items;
        activeIndex = -1;

        if (items.length === 0) {
          dropdown.innerHTML = `<div class="ac-empty-msg">Aucune entité trouvée pour "<strong>${escapeHtml(query)}</strong>"</div>`;
          dropdown.classList.add("open");
          return;
        }

        const maxDisplay = 60;
        const visibleItems = items.slice(0, maxDisplay);

        let html = visibleItems.map((item, idx) => {
          const stateLabel = item.unit ? `${item.state} ${item.unit}` : (item.state || "");
          return `
            <div class="ac-item" data-id="${escapeHtml(item.id)}" data-index="${idx}">
              <div class="ac-item-content">
                <div class="ac-item-name">${highlightMatches(item.name, query)}</div>
                <div class="ac-item-id">${highlightMatches(item.id, query)}</div>
              </div>
              ${stateLabel ? `<div class="ac-item-badge">${escapeHtml(stateLabel)}</div>` : ""}
            </div>
          `;
        }).join("");

        if (items.length > maxDisplay) {
          html += `<div class="ac-empty-msg" style="font-size:11px; padding:8px;">+ ${items.length - maxDisplay} autres entités (tapez pour filtrer)</div>`;
        }

        dropdown.innerHTML = html;
        dropdown.classList.add("open");

        dropdown.querySelectorAll(".ac-item").forEach(itemEl => {
          itemEl.addEventListener("mousedown", (e) => {
            e.preventDefault();
            e.stopPropagation();
            selectEntity(itemEl.dataset.id);
          });
        });
      };

      const selectEntity = (entityId) => {
        input.value = entityId;
        dropdown.classList.remove("open");
        updateHint(entityId);
        if (onSelect) onSelect(entityId);
        input.dispatchEvent(new Event("change", { bubbles: true }));
      };

      input.addEventListener("input", (e) => {
        const val = e.target.value;
        renderDropdown(filterList(val), val);
        updateHint(val);
      });

      input.addEventListener("focus", () => {
        renderDropdown(filterList(input.value), input.value);
      });

      input.addEventListener("blur", () => {
        setTimeout(() => {
          dropdown.classList.remove("open");
        }, 220);
      });

      const wrapper = input.closest(".ac-wrapper");
      if (wrapper) {
        const toggleBtn = wrapper.querySelector(".ac-toggle-btn");
        if (toggleBtn) {
          toggleBtn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (dropdown.classList.contains("open")) {
              dropdown.classList.remove("open");
            } else {
              input.focus();
              renderDropdown(filterList(input.value), input.value);
            }
          });
        }

        const clearBtn = wrapper.querySelector(".ac-clear-btn");
        if (clearBtn) {
          clearBtn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            input.value = "";
            updateHint("");
            input.focus();
            renderDropdown(entities, "");
            if (onSelect) onSelect("");
          });
        }
      }

      input.addEventListener("keydown", (e) => {
        if (!dropdown.classList.contains("open")) {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            renderDropdown(filterList(input.value), input.value);
          }
          return;
        }

        const domItems = dropdown.querySelectorAll(".ac-item");
        if (domItems.length === 0) return;

        if (e.key === "ArrowDown") {
          e.preventDefault();
          activeIndex = (activeIndex + 1) % domItems.length;
          updateActive(domItems);
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          activeIndex = (activeIndex - 1 + domItems.length) % domItems.length;
          updateActive(domItems);
        } else if (e.key === "Enter") {
          if (activeIndex >= 0 && activeIndex < domItems.length) {
            e.preventDefault();
            selectEntity(domItems[activeIndex].dataset.id);
          }
        } else if (e.key === "Escape") {
          e.preventDefault();
          dropdown.classList.remove("open");
        }
      });

      const updateActive = (domItems) => {
        domItems.forEach((el, idx) => {
          if (idx === activeIndex) {
            el.classList.add("active");
            el.scrollIntoView({ block: "nearest" });
          } else {
            el.classList.remove("active");
          }
        });
      };
    }

    _renderModal() {
      const s = this._editingSchedule;
      if (!s) return;
      const isSolar = s.trigger_type === "solar_shading";

      // Récupérer la liste des entités disponibles dans Home Assistant
      const states = (this._hass && this._hass.states) ? this._hass.states : {};

      // 1. Liste enrichie des volets (cover.*)
      const coverEntities = Object.keys(states)
        .filter(k => k.startsWith("cover."))
        .map(k => {
          const st = states[k];
          const fn = (st.attributes && st.attributes.friendly_name) ? st.attributes.friendly_name : k;
          let stateDesc = st.state === "open" ? "Ouvert" : (st.state === "closed" ? "Fermé" : st.state);
          if (st.attributes && st.attributes.current_position !== undefined) {
            stateDesc += ` (${st.attributes.current_position}%)`;
          }
          return {
            id: k,
            name: fn,
            state: stateDesc,
            unit: ""
          };
        })
        .sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));

      // 2. Liste enrichie des capteurs de température (sensor.*)
      const tempSensorEntities = Object.keys(states)
        .filter(k => {
          if (!k.startsWith("sensor.")) return false;
          const st = states[k];
          const attrs = st.attributes || {};
          const unit = attrs.unit_of_measurement || "";
          const devClass = attrs.device_class || "";
          const fn = (attrs.friendly_name || "").toLowerCase();
          const lk = k.toLowerCase();

          const isTempUnit = unit === "°C" || unit === "°F" || unit === "K";
          const isTempClass = devClass === "temperature";
          const hasTempWord = lk.includes("temperature") || lk.includes("temp_") || lk.endsWith("_temp") || fn.includes("températ") || fn.includes("temperature");
          if (lk.includes("temps_de_fonctionnement") && !isTempUnit) return false;

          return isTempUnit || isTempClass || hasTempWord;
        })
        .map(k => {
          const st = states[k];
          const attrs = st.attributes || {};
          const fn = attrs.friendly_name || k;
          const unit = attrs.unit_of_measurement || "°C";
          return {
            id: k,
            name: fn,
            state: st.state !== undefined ? st.state : "",
            unit: unit
          };
        })
        .sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));

      // Fallback avec l'ensemble des sensors au cas où
      const allSensors = Object.keys(states)
        .filter(k => k.startsWith("sensor."))
        .map(k => {
          const st = states[k];
          const attrs = st.attributes || {};
          return {
            id: k,
            name: attrs.friendly_name || k,
            state: st.state !== undefined ? st.state : "",
            unit: attrs.unit_of_measurement || ""
          };
        })
        .sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));

      // Toutes entités pour les cibles générales
      const allEntitiesList = Object.keys(states)
        .map(k => {
          const st = states[k];
          return {
            id: k,
            name: (st.attributes && st.attributes.friendly_name) ? st.attributes.friendly_name : k,
            state: st.state || "",
            unit: (st.attributes && st.attributes.unit_of_measurement) ? st.attributes.unit_of_measurement : ""
          };
        })
        .sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));

      // 4. Liste enrichie des personnes / trackers pour les déclencheurs de présence
      const personEntities = [
        { id: "any", name: "👤 Toute personne / N'importe qui", state: "", unit: "" },
        ...Object.keys(states)
          .filter(k => k.startsWith("person.") || k.startsWith("device_tracker."))
          .map(k => {
            const st = states[k];
            const fn = (st.attributes && st.attributes.friendly_name) ? st.attributes.friendly_name : k;
            return {
              id: k,
              name: `${fn} (${k})`,
              state: st.state || "",
              unit: ""
            };
          })
          .sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }))
      ];

      // 5. Liste enrichie des zones disponibles
      const zoneEntities = Object.keys(states)
        .filter(k => k.startsWith("zone."))
        .map(k => {
          const st = states[k];
          const fn = (st.attributes && st.attributes.friendly_name) ? st.attributes.friendly_name : k.replace("zone.", "");
          return {
            id: k,
            name: `${fn} (${k})`,
            state: st.state || "",
            unit: ""
          };
        })
        .sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));

      const modalEl = document.createElement("div");
      modalEl.className = "modal-backdrop";
      modalEl.innerHTML = `
        <div class="modal">
          <h2>${s.id ? "Modifier la règle" : (isSolar ? "Nouveau Volet Solaire" : "Nouvelle Planification")}</h2>
          
          <div class="form-group">
            <label>Nom de la règle</label>
            <input type="text" class="form-control" id="modal-name" value="${s.name || ''}" placeholder="Ex: Volets Salon, Lumière Extérieure...">
          </div>

          ${isSolar ? `
            <div class="form-group">
              <label>
                Entité du Volet Roulant (cover.*)
                <span class="ac-count-badge">${coverEntities.length} volet${coverEntities.length > 1 ? 's' : ''}</span>
              </label>
              <div class="ac-wrapper" id="ac-cover-wrapper">
                <div class="ac-input-group">
                  <input type="text" class="form-control ac-input" id="modal-cover-id" 
                         placeholder="Tapez pour filtrer (ex: salon, rideau, volet)..." 
                         value="${s.cover_entity_id || ''}" autocomplete="off">
                  <div class="ac-controls">
                    <button type="button" class="ac-btn ac-clear-btn" title="Effacer la saisie">✕</button>
                    <button type="button" class="ac-btn ac-toggle-btn" title="Afficher tous les volets">▼</button>
                  </div>
                </div>
                <div class="ac-dropdown" id="ac-cover-dropdown"></div>
              </div>
              <div class="ac-selection-hint" id="ac-cover-hint" style="${s.cover_entity_id ? '' : 'display:none;'}">
                ${s.cover_entity_id && states[s.cover_entity_id] ? `
                  Sélectionné : <strong>${states[s.cover_entity_id].attributes?.friendly_name || s.cover_entity_id}</strong>
                  ${states[s.cover_entity_id].attributes?.current_position !== undefined ? `(${states[s.cover_entity_id].attributes.current_position}%)` : `(${states[s.cover_entity_id].state})`}
                ` : ''}
              </div>
            </div>

            <div class="form-group">
              <label>Exposition de la façade / fenêtre</label>
              <select class="form-control" id="modal-orientation">
                ${COMPASS_OPTIONS.map(opt => `<option value="${opt.val}" ${opt.val === s.orientation ? 'selected' : ''}>${opt.label}</option>`).join("")}
              </select>
            </div>

            <div class="form-group">
              <label>
                Capteur de Température de référence (sensor.*)
                <span class="ac-count-badge">${tempSensorEntities.length} capteur${tempSensorEntities.length > 1 ? 's' : ''}</span>
              </label>
              <div class="ac-wrapper" id="ac-temp-wrapper">
                <div class="ac-input-group">
                  <input type="text" class="form-control ac-input" id="modal-temp-sensor" 
                         placeholder="Tapez pour filtrer (ex: salon, sonde, ext)..." 
                         value="${s.temperature_sensor_id || ''}" autocomplete="off">
                  <div class="ac-controls">
                    <button type="button" class="ac-btn ac-clear-btn" title="Effacer la saisie">✕</button>
                    <button type="button" class="ac-btn ac-toggle-btn" title="Afficher tous les capteurs">▼</button>
                  </div>
                </div>
                <div class="ac-dropdown" id="ac-temp-dropdown"></div>
              </div>
              <div class="ac-selection-hint" id="ac-temp-hint" style="${s.temperature_sensor_id ? '' : 'display:none;'}">
                ${s.temperature_sensor_id && states[s.temperature_sensor_id] ? `
                  Sélectionné : <strong>${states[s.temperature_sensor_id].attributes?.friendly_name || s.temperature_sensor_id}</strong>
                  (${states[s.temperature_sensor_id].state} ${states[s.temperature_sensor_id].attributes?.unit_of_measurement || '°C'})
                ` : ''}
              </div>
            </div>

            <div class="form-group">
              <label>Seuil de Température déclencheur (°C)</label>
              <input type="number" step="0.5" class="form-control" id="modal-temp-thresh" value="${s.temperature_threshold || 24}">
            </div>

            <div style="display: flex; gap: 12px;">
              <div class="form-group" style="flex:1;">
                <label>Position Fermeture Solaire (%)</label>
                <input type="number" min="0" max="100" class="form-control" id="modal-pos-shading" value="${s.shading_position !== undefined ? s.shading_position : 20}">
              </div>
              <div class="form-group" style="flex:1;">
                <label>Position Réouverture (%)</label>
                <input type="number" min="0" max="100" class="form-control" id="modal-pos-open" value="${s.open_position !== undefined ? s.open_position : 100}">
              </div>
            </div>
          ` : `
            <!-- 1. Déclenchement Temporel, Solaire ou Zone -->
            <div class="form-group">
              <label>Moment du déclenchement</label>
              <div class="segmented-control" id="ctrl-time-type" style="display: flex; flex-wrap: wrap; gap: 6px;">
                <button type="button" class="segmented-btn ${(s.time_type === 'fixed' || !s.time_type) ? 'active' : ''}" data-type="fixed"><ha-icon icon="mdi:clock-outline"></ha-icon> <span>Heure fixe</span></button>
                <button type="button" class="segmented-btn ${s.time_type === 'sunrise' ? 'active' : ''}" data-type="sunrise"><ha-icon icon="mdi:weather-sunset-up"></ha-icon> <span>Lever soleil</span></button>
                <button type="button" class="segmented-btn ${s.time_type === 'sunset' ? 'active' : ''}" data-type="sunset"><ha-icon icon="mdi:weather-sunset-down"></ha-icon> <span>Coucher soleil</span></button>
                <button type="button" class="segmented-btn ${s.time_type === 'zone_enter' ? 'active' : ''}" data-type="zone_enter"><ha-icon icon="mdi:map-marker-radius"></ha-icon> <span>Arrivée zone</span></button>
                <button type="button" class="segmented-btn ${s.time_type === 'zone_leave' ? 'active' : ''}" data-type="zone_leave"><ha-icon icon="mdi:map-marker-minus"></ha-icon> <span>Sortie zone</span></button>
              </div>

              <div id="section-fixed-time" style="${(s.time_type === 'fixed' || !s.time_type) ? '' : 'display:none;'}">
                <input type="time" class="form-control" id="modal-time" value="${s.time || '07:30'}">
              </div>

              <div id="section-solar-offset" style="${(s.time_type === 'sunrise' || s.time_type === 'sunset') ? '' : 'display:none;'}">
                <div style="display:flex; align-items:center; gap: 10px;">
                  <label style="margin:0; font-size:12px; white-space:nowrap;">Décalage (minutes) :</label>
                  <input type="number" class="form-control" id="modal-solar-offset" value="${s.solar_offset_minutes !== undefined ? s.solar_offset_minutes : 0}" step="5" style="max-width: 120px;">
                  <span style="font-size:12px; color:#94a3b8;">(- avant, + après)</span>
                </div>
              </div>

              <div id="section-zone-trigger" style="${(s.time_type === 'zone_enter' || s.time_type === 'zone_leave') ? '' : 'display:none;'}">
                <div style="display:flex; gap: 12px; margin-top: 10px;">
                  <div style="flex:1;">
                    <label style="font-size:12px; font-weight:600; color:#cbd5e1; margin-bottom:4px; display:block;">
                      Personne concernée
                      <span class="ac-count-badge">${personEntities.length}</span>
                    </label>
                    <div class="ac-wrapper" id="ac-person-wrapper">
                      <div class="ac-input-group">
                        <input type="text" class="form-control ac-input" id="modal-zone-person" 
                               placeholder="👤 Toute personne ou nom..." 
                               value="${s.zone_person_id || 'any'}" autocomplete="off">
                        <div class="ac-controls">
                          <button type="button" class="ac-btn ac-clear-btn" title="Effacer la saisie">✕</button>
                          <button type="button" class="ac-btn ac-toggle-btn" title="Afficher la liste">▼</button>
                        </div>
                      </div>
                      <div class="ac-dropdown" id="ac-person-dropdown"></div>
                    </div>
                    <div class="ac-selection-hint" id="ac-person-hint">
                      Sélectionné : <strong>${(s.zone_person_id === 'any' || !s.zone_person_id) ? '👤 Toute personne / N\'importe qui' : (states[s.zone_person_id]?.attributes?.friendly_name || s.zone_person_id)}</strong>
                    </div>
                  </div>
                  <div style="flex:1;">
                    <label style="font-size:12px; font-weight:600; color:#cbd5e1; margin-bottom:4px; display:block;">
                      Zone cible
                      <span class="ac-count-badge">${zoneEntities.length}</span>
                    </label>
                    <div class="ac-wrapper" id="ac-zone-wrapper">
                      <div class="ac-input-group">
                        <input type="text" class="form-control ac-input" id="modal-zone-id" 
                               placeholder="📍 Zone (ex: zone.home)..." 
                               value="${s.zone_id || 'zone.home'}" autocomplete="off">
                        <div class="ac-controls">
                          <button type="button" class="ac-btn ac-clear-btn" title="Effacer la saisie">✕</button>
                          <button type="button" class="ac-btn ac-toggle-btn" title="Afficher la liste">▼</button>
                        </div>
                      </div>
                      <div class="ac-dropdown" id="ac-zone-dropdown"></div>
                    </div>
                    <div class="ac-selection-hint" id="ac-zone-hint">
                      Sélectionné : <strong>${states[s.zone_id || 'zone.home']?.attributes?.friendly_name || s.zone_id || 'Maison (zone.home)'}</strong>
                    </div>
                  </div>
                </div>
                <div class="info-banner" style="margin-top: 8px;">
                  📍 Déclenchement instantané dès qu'une personne franchit la zone (respecte les jours sélectionnés).
                </div>
              </div>
            </div>

            <!-- 2. Sélecteur de Fréquence & Périodicité -->
            <div class="form-group">
              <label>Fréquence & Répétition</label>
              <div class="segmented-control" id="ctrl-recurrence-mode">
                <button type="button" class="segmented-btn ${(s.recurrence_mode === 'every' || !s.recurrence_mode) ? 'active' : ''}" data-mode="every">🔁 Tous les</button>
                <button type="button" class="segmented-btn ${s.recurrence_mode === 'next' ? 'active' : ''}" data-mode="next">⏩ Prochain</button>
                <button type="button" class="segmented-btn ${s.recurrence_mode === 'date' ? 'active' : ''}" data-mode="date">📅 Date</button>
              </div>

              <!-- Mode [ 🔁 Tous les ] -->
              <div id="freq-section-every" style="${(s.recurrence_mode === 'every' || !s.recurrence_mode) ? '' : 'display:none;'}">
                <div class="weekday-selector" id="weekday-selector-every">
                  ${WEEKDAYS_LABELS.map(w => {
                    const isSel = (s.weekdays || [0,1,2,3,4]).includes(w.id);
                    return `<div class="day-btn ${isSel ? 'selected' : ''}" data-day="${w.id}">${w.label}</div>`;
                  }).join("")}
                </div>
                <div class="info-banner">Exécution récurrente chaque semaine aux jours choisis.</div>
              </div>

              <!-- Mode [ ⏩ Prochain ] -->
              <div id="freq-section-next" style="${s.recurrence_mode === 'next' ? '' : 'display:none;'}">
                <div class="weekday-selector" id="weekday-selector-next">
                  ${WEEKDAYS_LABELS.map(w => {
                    const isSel = (s.weekdays || [0]).includes(w.id);
                    return `<div class="day-btn ${isSel ? 'selected' : ''}" data-day="${w.id}">${w.label}</div>`;
                  }).join("")}
                </div>
                <div class="info-banner">S'exécutera une seule fois lors du prochain jour sélectionné.</div>
              </div>

              <!-- Mode [ 📅 Date ] -->
              <div id="freq-section-date" style="${s.recurrence_mode === 'date' ? '' : 'display:none;'}">
                <div style="display:flex; gap: 12px; margin-bottom: 12px;">
                  <div style="flex:1;">
                    <label style="font-size:12px;">Mois</label>
                    <select class="form-control" id="modal-date-month">
                      ${MONTHS_LIST.map(m => `<option value="${m.val}" ${m.val === parseInt(s.month || (new Date().getMonth() + 1), 10) ? 'selected' : ''}>${m.label}</option>`).join("")}
                    </select>
                  </div>
                  <div style="flex:1;">
                    <label style="font-size:12px;">Année</label>
                    <select class="form-control" id="modal-date-year">
                      <option value="every_year" ${s.year === 'every_year' ? 'selected' : ''}>🔁 Chaque année (Annuel)</option>
                      ${[2026, 2027, 2028, 2029, 2030].map(y => `<option value="${y}" ${String(s.year || new Date().getFullYear()) === String(y) ? 'selected' : ''}>${y}</option>`).join("")}
                    </select>
                  </div>
                </div>

                <!-- Option C Sub-Tabs -->
                <div class="sub-tabs">
                  <button type="button" class="sub-tab-btn ${s.date_selection_type !== 'weekdays' ? 'active' : ''}" id="tab-date-exact">📍 Jour précis (1 à 31)</button>
                  <button type="button" class="sub-tab-btn ${s.date_selection_type === 'weekdays' ? 'active' : ''}" id="tab-date-weekdays">🗓️ Jours de la semaine</button>
                </div>

                <!-- Sub-tab Exact day -->
                <div id="subtab-exact-content" style="${s.date_selection_type !== 'weekdays' ? '' : 'display:none;'}">
                  <div style="display:flex; align-items:center; gap: 10px;">
                    <label style="margin:0; font-size:12px; white-space:nowrap;">Numéro du jour (1-31) :</label>
                    <select class="form-control" id="modal-date-day" style="max-width: 100px;">
                      ${Array.from({ length: 31 }, (_, i) => i + 1).map(d => `<option value="${d}" ${d === parseInt(s.day_of_month || new Date().getDate(), 10) ? 'selected' : ''}>${d < 10 ? '0' + d : d}</option>`).join("")}
                    </select>
                  </div>
                </div>

                <!-- Sub-tab Weekdays in month -->
                <div id="subtab-weekdays-content" style="${s.date_selection_type === 'weekdays' ? '' : 'display:none;'}">
                  <div class="weekday-selector" id="weekday-selector-date">
                    ${WEEKDAYS_LABELS.map(w => {
                      const isSel = (s.weekdays || [0,1,2,3,4]).includes(w.id);
                      return `<div class="day-btn ${isSel ? 'selected' : ''}" data-day="${w.id}">${w.label}</div>`;
                    }).join("")}
                  </div>
                  <div class="info-banner">S'exécutera tous les jours choisis du mois configuré.</div>
                </div>
              </div>
            </div>

            <!-- Option B: Action post-exécution pour exécution unique (Prochain ou Date fixe) -->
            <div class="form-group" id="group-post-exec" style="${(s.recurrence_mode === 'next' || (s.recurrence_mode === 'date' && s.year !== 'every_year')) ? '' : 'display:none;'}">
              <label>Action après l'exécution de cette règle unique</label>
              <select class="form-control" id="modal-post-exec">
                <option value="disable" ${s.post_execution_action !== 'delete' ? 'selected' : ''}>⏸️ Désactiver la règle (Conserver dans la liste)</option>
                <option value="delete" ${s.post_execution_action === 'delete' ? 'selected' : ''}>🗑️ Supprimer automatiquement la règle</option>
              </select>
            </div>

            <!-- 3. Cible et Action -->
            <div class="form-group">
              <label>Type de Cible</label>
              <select class="form-control" id="modal-target-type">
                <option value="label" ${s.target_type === 'label' ? 'selected' : ''}>🏷️ Étiquette (Label HA)</option>
                <option value="entity" ${s.target_type === 'entity' ? 'selected' : ''}>💡 Entité spécifique</option>
                <option value="area" ${s.target_type === 'area' ? 'selected' : ''}>🏠 Pièce (Area)</option>
                <option value="script" ${s.target_type === 'script' ? 'selected' : ''}>📜 Script</option>
                <option value="automation" ${s.target_type === 'automation' ? 'selected' : ''}>⚙️ Automatisation</option>
                <option value="scene" ${s.target_type === 'scene' ? 'selected' : ''}>🎬 Scène</option>
                <option value="reminder" ${s.target_type === 'reminder' ? 'selected' : ''}>🔔 Rappel / Notification</option>
              </select>
            </div>

            <!-- Cible Standard -->
            <div id="section-standard-target" style="${s.target_type === 'reminder' ? 'display:none;' : ''}">
              <div class="form-group" id="group-target-val">
                <label id="label-target-val">Cible</label>
                <div class="ac-wrapper" id="ac-target-wrapper">
                  <div class="ac-input-group">
                    <input type="text" class="form-control ac-input" id="modal-target-val" 
                           placeholder="Saisissez ou recherchez la cible..." 
                           value="${s.target_type !== 'reminder' ? (s.target_value || '') : ''}" autocomplete="off">
                    <div class="ac-controls">
                      <button type="button" class="ac-btn ac-clear-btn" title="Effacer la saisie">✕</button>
                      <button type="button" class="ac-btn ac-toggle-btn" title="Afficher la liste">▼</button>
                    </div>
                  </div>
                  <div class="ac-dropdown" id="ac-target-dropdown"></div>
                </div>
                <div class="ac-selection-hint" id="ac-target-hint" style="${s.target_value && s.target_type !== 'reminder' ? '' : 'display:none;'}">
                  ${s.target_value && states[s.target_value] ? `
                    Sélectionné : <strong>${states[s.target_value].attributes?.friendly_name || s.target_value}</strong>
                  ` : ''}
                </div>
              </div>

              <div class="form-group">
                <label>Action à exécuter</label>
                <select class="form-control" id="modal-action-service">
                  <option value="turn_on" ${s.action_service === 'turn_on' ? 'selected' : ''}>Allumer / Activer (turn_on)</option>
                  <option value="turn_off" ${s.action_service === 'turn_off' ? 'selected' : ''}>Éteindre / Désactiver (turn_off)</option>
                  <option value="toggle" ${s.action_service === 'toggle' ? 'selected' : ''}>Basculer (toggle)</option>
                  <option value="open_cover" ${s.action_service === 'open_cover' ? 'selected' : ''}>Ouvrir volet (open_cover)</option>
                  <option value="close_cover" ${s.action_service === 'close_cover' ? 'selected' : ''}>Fermer volet (close_cover)</option>
                  <option value="trigger" ${s.action_service === 'trigger' ? 'selected' : ''}>Déclencher (trigger)</option>
                </select>
              </div>
            </div>

            <!-- Section Rappel / Multi-Canal (SMS Free, Telegram, App Mobile, Persistant) -->
            <div id="section-reminder-target" style="${s.target_type === 'reminder' ? '' : 'display:none;'}">
              <div class="form-group">
                <label>Canal d'envoi du Rappel</label>
                <select class="form-control" id="modal-reminder-channel">
                  ${REMINDER_CHANNELS.map(ch => `<option value="${ch.id}" ${s.reminder_channel === ch.id ? 'selected' : ''}>${ch.label}</option>`).join("")}
                </select>
              </div>

              <div class="form-group">
                <label>Message du Rappel</label>
                <textarea class="form-control" id="modal-reminder-msg" rows="3" placeholder="Ex: Penser à sortir les poubelles, arroser les plantes, rendez-vous...">${s.reminder_message || ''}</textarea>
              </div>
            </div>

            <div class="form-group">
              <label>Gestion des Jours Fériés</label>
              <select class="form-control" id="modal-holiday-mode">
                <option value="always" ${s.holiday_mode === 'always' ? 'selected' : ''}>Actif tous les jours</option>
                <option value="exclude" ${s.holiday_mode === 'exclude' ? 'selected' : ''}>Ne pas exécuter les jours fériés</option>
                <option value="weekend" ${s.holiday_mode === 'weekend' ? 'selected' : ''}>Comportement Week-end les jours fériés</option>
                <option value="only_holidays" ${s.holiday_mode === 'only_holidays' ? 'selected' : ''}>Uniquement les jours fériés</option>
              </select>
            </div>
          `}

          <div style="display:flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
            <button class="btn" id="modal-cancel"><ha-icon icon="mdi:close"></ha-icon> <span>Annuler</span></button>
            <button class="btn btn-primary" id="modal-save"><ha-icon icon="mdi:check"></ha-icon> <span>Enregistrer</span></button>
          </div>
        </div>
      `;

      // Retirer tout modal existant avant d'ajouter le nouveau
      const existing = this.shadowRoot.querySelector(".modal-backdrop");
      if (existing) existing.remove();

      this.shadowRoot.appendChild(modalEl);

      // Fermeture sur clic extérieur
      modalEl.addEventListener("click", (e) => {
        if (e.target === modalEl) this._closeModal();
      });

      // Initialisation de l'autocomplétion
      if (isSolar) {
        this._setupEntityAutocomplete(modalEl, {
          inputId: "modal-cover-id",
          dropdownId: "ac-cover-dropdown",
          hintId: "ac-cover-hint",
          entities: coverEntities,
          onSelect: (selectedId) => {
            const nameInput = modalEl.querySelector("#modal-name");
            if (nameInput && (!nameInput.value || nameInput.value === "Nouveau Volet Solaire" || nameInput.value === "Volet Solaire")) {
              const matched = coverEntities.find(c => c.id === selectedId);
              if (matched) {
                nameInput.value = `${matched.name} - Suivi Solaire`;
              }
            }
          }
        });

        this._setupEntityAutocomplete(modalEl, {
          inputId: "modal-temp-sensor",
          dropdownId: "ac-temp-dropdown",
          hintId: "ac-temp-hint",
          entities: tempSensorEntities,
          fallbackEntities: allSensors
        });
      } else {
        const setupTargetAc = () => {
          const type = modalEl.querySelector("#modal-target-type")?.value || "entity";
          if (type === "reminder") return;
          let entitiesList = allEntitiesList;
          if (type === "script") entitiesList = allEntitiesList.filter(e => e.id.startsWith("script."));
          else if (type === "automation") entitiesList = allEntitiesList.filter(e => e.id.startsWith("automation."));
          else if (type === "scene") entitiesList = allEntitiesList.filter(e => e.id.startsWith("scene."));
          else if (type === "entity") entitiesList = allEntitiesList;
          else entitiesList = [];

          this._setupEntityAutocomplete(modalEl, {
            inputId: "modal-target-val",
            dropdownId: "ac-target-dropdown",
            hintId: "ac-target-hint",
            entities: entitiesList
          });
        };

        setupTargetAc();

        // Autocomplétion Personne et Zone pour déclencheur de présence
        this._setupEntityAutocomplete(modalEl, {
          inputId: "modal-zone-person",
          dropdownId: "ac-person-dropdown",
          hintId: "ac-person-hint",
          entities: personEntities,
        });

        this._setupEntityAutocomplete(modalEl, {
          inputId: "modal-zone-id",
          dropdownId: "ac-zone-dropdown",
          hintId: "ac-zone-hint",
          entities: zoneEntities,
        });

        // 1. Boutons Type de Déclenchement (fixed / sunrise / sunset / zone_enter / zone_leave)
        modalEl.querySelectorAll("#ctrl-time-type .segmented-btn").forEach(btn => {
          btn.addEventListener("click", (e) => {
            modalEl.querySelectorAll("#ctrl-time-type .segmented-btn").forEach(b => b.classList.remove("active"));
            e.currentTarget.classList.add("active");
            const type = e.currentTarget.dataset.type;
            const secFixed = modalEl.querySelector("#section-fixed-time");
            const secSolar = modalEl.querySelector("#section-solar-offset");
            const secZone = modalEl.querySelector("#section-zone-trigger");
            if (secFixed) secFixed.style.display = (type === "fixed") ? "" : "none";
            if (secSolar) secSolar.style.display = (type === "sunrise" || type === "sunset") ? "" : "none";
            if (secZone) secZone.style.display = (type === "zone_enter" || type === "zone_leave") ? "" : "none";
          });
        });

        // 2. Boutons Fréquence & Répétition (every / next / date)
        const updatePostExecVisibility = () => {
          const activeRecBtn = modalEl.querySelector("#ctrl-recurrence-mode .segmented-btn.active");
          const mode = activeRecBtn ? activeRecBtn.dataset.mode : "every";
          const yearVal = modalEl.querySelector("#modal-date-year")?.value;
          const postExecGroup = modalEl.querySelector("#group-post-exec");
          if (!postExecGroup) return;
          if (mode === "next" || (mode === "date" && yearVal !== "every_year")) {
            postExecGroup.style.display = "";
          } else {
            postExecGroup.style.display = "none";
          }
        };

        modalEl.querySelectorAll("#ctrl-recurrence-mode .segmented-btn").forEach(btn => {
          btn.addEventListener("click", (e) => {
            modalEl.querySelectorAll("#ctrl-recurrence-mode .segmented-btn").forEach(b => b.classList.remove("active"));
            e.currentTarget.classList.add("active");
            const mode = e.currentTarget.dataset.mode;
            const secEvery = modalEl.querySelector("#freq-section-every");
            const secNext = modalEl.querySelector("#freq-section-next");
            const secDate = modalEl.querySelector("#freq-section-date");
            if (secEvery) secEvery.style.display = mode === "every" ? "" : "none";
            if (secNext) secNext.style.display = mode === "next" ? "" : "none";
            if (secDate) secDate.style.display = mode === "date" ? "" : "none";
            updatePostExecVisibility();
          });
        });

        modalEl.querySelector("#modal-date-year")?.addEventListener("change", updatePostExecVisibility);

        // 3. Sub-tabs Option C (Jour précis vs Jours de la semaine)
        const tabExact = modalEl.querySelector("#tab-date-exact");
        const tabWeekdays = modalEl.querySelector("#tab-date-weekdays");
        const contentExact = modalEl.querySelector("#subtab-exact-content");
        const contentWeekdays = modalEl.querySelector("#subtab-weekdays-content");

        if (tabExact && tabWeekdays) {
          tabExact.addEventListener("click", () => {
            tabExact.classList.add("active");
            tabWeekdays.classList.remove("active");
            if (contentExact) contentExact.style.display = "";
            if (contentWeekdays) contentWeekdays.style.display = "none";
          });
          tabWeekdays.addEventListener("click", () => {
            tabWeekdays.classList.add("active");
            tabExact.classList.remove("active");
            if (contentExact) contentExact.style.display = "none";
            if (contentWeekdays) contentWeekdays.style.display = "";
          });
        }

        // 4. Bascule Type de Cible (Standard vs Rappel Multi-canal)
        modalEl.querySelector("#modal-target-type")?.addEventListener("change", (e) => {
          const val = e.target.value;
          const secStd = modalEl.querySelector("#section-standard-target");
          const secRem = modalEl.querySelector("#section-reminder-target");
          if (val === "reminder") {
            if (secStd) secStd.style.display = "none";
            if (secRem) secRem.style.display = "";
          } else {
            if (secStd) secStd.style.display = "";
            if (secRem) secRem.style.display = "none";
            setupTargetAc();
          }
        });
      }

      // Gestion des boutons de jours de semaine (toutes sections confondues)
      const selectedWeekdays = new Set(s.weekdays || [0, 1, 2, 3, 4]);
      modalEl.querySelectorAll(".day-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const day = parseInt(e.currentTarget.dataset.day, 10);
          const parent = e.currentTarget.parentElement;
          if (parent && parent.id === "weekday-selector-next") {
            parent.querySelectorAll(".day-btn").forEach(b => b.classList.remove("selected"));
            e.currentTarget.classList.add("selected");
            selectedWeekdays.clear();
            selectedWeekdays.add(day);
          } else {
            if (selectedWeekdays.has(day)) {
              selectedWeekdays.delete(day);
              e.currentTarget.classList.remove("selected");
            } else {
              selectedWeekdays.add(day);
              e.currentTarget.classList.add("selected");
            }
          }
        });
      });

      modalEl.querySelector("#modal-cancel").addEventListener("click", () => this._closeModal());
      modalEl.querySelector("#modal-save").addEventListener("click", () => {
        s.name = modalEl.querySelector("#modal-name").value.trim() || (isSolar ? "Volet Solaire" : "Planification");
        if (isSolar) {
          s.cover_entity_id = modalEl.querySelector("#modal-cover-id").value.trim();
          s.orientation = modalEl.querySelector("#modal-orientation").value;
          s.temperature_sensor_id = modalEl.querySelector("#modal-temp-sensor").value.trim();
          s.temperature_threshold = parseFloat(modalEl.querySelector("#modal-temp-thresh").value);
          s.shading_position = parseInt(modalEl.querySelector("#modal-pos-shading").value, 10);
          s.open_position = parseInt(modalEl.querySelector("#modal-pos-open").value, 10);
        } else {
          // Time type & offset / zone
          const activeTimeBtn = modalEl.querySelector("#ctrl-time-type .segmented-btn.active");
          s.time_type = activeTimeBtn ? activeTimeBtn.dataset.type : "fixed";
          if (s.time_type === "fixed") {
            s.time = modalEl.querySelector("#modal-time").value || "07:30";
          } else if (s.time_type === "sunrise" || s.time_type === "sunset") {
            s.solar_offset_minutes = parseInt(modalEl.querySelector("#modal-solar-offset").value || "0", 10);
          } else if (s.time_type === "zone_enter" || s.time_type === "zone_leave") {
            s.zone_person_id = modalEl.querySelector("#modal-zone-person").value.trim() || "any";
            s.zone_id = modalEl.querySelector("#modal-zone-id").value.trim() || "zone.home";
          }

          // Recurrence mode
          const activeRecBtn = modalEl.querySelector("#ctrl-recurrence-mode .segmented-btn.active");
          s.recurrence_mode = activeRecBtn ? activeRecBtn.dataset.mode : "every";

          if (s.recurrence_mode === "every") {
            s.weekdays = Array.from(selectedWeekdays).sort();
          } else if (s.recurrence_mode === "next") {
            s.weekdays = Array.from(selectedWeekdays).sort();
            s.post_execution_action = modalEl.querySelector("#modal-post-exec")?.value || "disable";
          } else if (s.recurrence_mode === "date") {
            s.month = parseInt(modalEl.querySelector("#modal-date-month").value, 10);
            const yrVal = modalEl.querySelector("#modal-date-year").value;
            s.year = yrVal === "every_year" ? "every_year" : parseInt(yrVal, 10);

            const isExact = modalEl.querySelector("#tab-date-exact")?.classList.contains("active");
            s.date_selection_type = isExact ? "exact_day" : "weekdays";

            if (isExact) {
              s.day_of_month = parseInt(modalEl.querySelector("#modal-date-day").value, 10);
            } else {
              s.weekdays = Array.from(selectedWeekdays).sort();
            }

            if (s.year !== "every_year") {
              s.post_execution_action = modalEl.querySelector("#modal-post-exec")?.value || "disable";
            }
          }

          s.target_type = modalEl.querySelector("#modal-target-type").value;
          if (s.target_type === "reminder") {
            s.reminder_channel = modalEl.querySelector("#modal-reminder-channel").value;
            s.reminder_message = modalEl.querySelector("#modal-reminder-msg").value.trim();
            s.target_value = s.reminder_channel;
            s.action_service = "notify";
            s.action_data = {
              channel: s.reminder_channel,
              message: s.reminder_message
            };
          } else {
            s.target_value = modalEl.querySelector("#modal-target-val").value.trim();
            s.action_service = modalEl.querySelector("#modal-action-service").value;
            s.action_data = {
              service: s.action_service,
            };
          }

          s.holiday_mode = modalEl.querySelector("#modal-holiday-mode").value;
        }
        this._saveScheduleFromModal();
      });
    }
  }

  customElements.define(PANEL_NAME, DomolinkPlanificationPanel);

  // =========================================================================
  // CARTE LOVELACE PERSONNALISÉE (domolink-planification-card)
  // =========================================================================
  class DomolinkPlanificationCard extends HTMLElement {
    set hass(hass) {
      this._hass = hass;
      if (!this._root) {
        this._root = this.attachShadow({ mode: "open" });
        this._render();
      }
    }

    setConfig(config) {
      this._config = config || {};
    }

    getCardSize() {
      return 3;
    }

    _render() {
      if (!this._root) return;
      this._root.innerHTML = `
        <style>
          :host {
            display: block;
          }
          ha-card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 16px;
            color: #f1f5f9;
          }
          .title {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .link-btn {
            display: inline-block;
            margin-top: 12px;
            font-size: 13px;
            color: #60a5fa;
            text-decoration: none;
            font-weight: 600;
          }
        </style>
        <ha-card>
          <div class="title">
            <ha-icon icon="mdi:calendar-clock" style="--mdc-icon-size:22px; color:#38bdf8;"></ha-icon>
            <span>${this._config.title || "DomoLink-Planification"}</span>
          </div>
          <p style="margin:0; font-size: 13px; color: #94a3b8;">
            Moteur d'automatisation & suivi solaire actif.
          </p>
          <a href="/domolink-planification" class="link-btn"><ha-icon icon="mdi:open-in-app" style="--mdc-icon-size:16px; vertical-align:middle; margin-right:4px;"></ha-icon> Ouvrir le panneau de planification</a>
        </ha-card>
      `;
    }
  }

  customElements.define(CARD_NAME, DomolinkPlanificationCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_NAME,
    name: "DomoLink-Planification Card",
    description: "Affichage et gestion des planifications et volets solaires DomoLink",
  });

  // =========================================================================
  // BADGE BLEU FRANCE DANS LA BARRE LATÉRALE (SIDEBAR)
  // =========================================================================
  function applySidebarBadge() {
    function getDeepRoots(node, list = []) {
      if (!node) return list;
      if (node.shadowRoot) {
        list.push(node.shadowRoot);
        getDeepRoots(node.shadowRoot, list);
      }
      for (const child of node.children || []) {
        getDeepRoots(child, list);
      }
      return list;
    }

    try {
      const roots = [document, ...getDeepRoots(document.body)];
      for (const r of roots) {
        if (!r.querySelectorAll) continue;

        // 1. Injection CSS dans les shadowRoots de la sidebar
        const sidebars = r.querySelectorAll("ha-sidebar");
        for (const sb of sidebars) {
          const sRoot = sb.shadowRoot || sb;
          if (sRoot && !sRoot.querySelector("#domolink-sidebar-badge-css")) {
            const style = document.createElement("style");
            style.id = "domolink-sidebar-badge-css";
            style.textContent = `
              a[data-panel="domolink-planification"] .item-text,
              a[href*="domolink-planification"] .item-text,
              paper-icon-item[data-panel="domolink-planification"] .item-text,
              ha-list-item[data-panel="domolink-planification"] .item-text {
                background: #002395 !important; /* Bleu France */
                color: #ffffff !important;
                border-radius: 12px !important;
                font-weight: 700 !important;
                font-size: 13px !important;
                padding: 3px 10px !important;
                display: inline-block !important;
                box-shadow: 0 2px 6px rgba(0, 35, 149, 0.45) !important;
                letter-spacing: 0.3px !important;
              }
              a[data-panel="domolink-planification"]:hover .item-text,
              a[href*="domolink-planification"]:hover .item-text {
                background: #001b73 !important;
                box-shadow: 0 3px 10px rgba(0, 35, 149, 0.65) !important;
              }
            `;
            sRoot.appendChild(style);
          }
        }

        // 2. Application directe de styles en ligne sur les éléments de texte trouvés
        const targets = r.querySelectorAll(`
          a[data-panel="domolink-planification"] .item-text,
          a[href*="domolink-planification"] .item-text,
          paper-icon-item[data-panel="domolink-planification"] .item-text,
          ha-list-item[data-panel="domolink-planification"] .item-text
        `);
        targets.forEach(el => {
          el.style.setProperty("background", "#002395", "important");
          el.style.setProperty("color", "#ffffff", "important");
          el.style.setProperty("border-radius", "12px", "important");
          el.style.setProperty("font-weight", "700", "important");
          el.style.setProperty("font-size", "13px", "important");
          el.style.setProperty("padding", "3px 10px", "important");
          el.style.setProperty("display", "inline-block", "important");
          el.style.setProperty("box-shadow", "0 2px 6px rgba(0, 35, 149, 0.45)", "important");
        });
      }
    } catch (e) {
      // Silencieux
    }
  }

  // Appliquer le badge et assurer sa persistance lors des navigations
  if (typeof window !== "undefined") {
    applySidebarBadge();
    setTimeout(applySidebarBadge, 300);
    setTimeout(applySidebarBadge, 1000);
    setTimeout(applySidebarBadge, 2500);
    setInterval(applySidebarBadge, 4000);
    window.addEventListener("location-changed", () => setTimeout(applySidebarBadge, 200));
  }

  console.info(
    `%c DOMOLINK-PLANIFICATION %c v1.2.0 chargé avec succès `,
    "background: #002395; color: #fff; font-weight: bold; border-radius: 4px 0 0 4px;",
    "background: #1e293b; color: #60a5fa; border-radius: 0 4px 4px 0;"
  );
})();
