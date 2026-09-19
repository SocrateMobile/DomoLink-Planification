/**
 * DomoLink-Planification — Panneau Tactile & Carte Lovelace (v1.0.0)
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

  const STYLES = `
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #f1f5f9;
      background: #0b0f19;
      min-height: 100vh;
      box-sizing: border-box;
      padding: 24px;
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
      font-size: 32px;
      width: 48px;
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      border-radius: 12px;
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
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
    }
    .tab {
      padding: 10px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 600;
      color: #94a3b8;
      transition: all 0.2s ease;
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

    /* Modal Dialog */
    .modal-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 20px;
    }
    .modal {
      background: #1e293b;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 16px;
      width: 100%;
      max-width: 600px;
      max-height: 90vh;
      overflow-y: auto;
      padding: 24px;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6);
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
      background: rgba(15, 23, 42, 0.8);
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
    }
    .day-btn.selected {
      background: #3b82f6;
      color: #fff;
      border-color: #60a5fa;
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
      z-index: 2000;
      display: flex;
      align-items: center;
      gap: 10px;
      transform: translateY(100px);
      opacity: 0;
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .toast.show {
      transform: translateY(0);
      opacity: 1;
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

    _openScheduleModal(sched = null, isSolar = false) {
      this._editingSchedule = sched ? JSON.parse(JSON.stringify(sched)) : {
        id: "",
        name: isSolar ? "Volet Salon - Suivi Solaire" : "Nouvelle Planification",
        enabled: true,
        trigger_type: isSolar ? "solar_shading" : "time",
        time: "07:30",
        weekdays: [0, 1, 2, 3, 4],
        target_type: isSolar ? "entity" : "label",
        target_value: "",
        cover_entity_id: "",
        orientation: "S",
        temperature_sensor_id: "",
        temperature_threshold: 24.0,
        shading_position: 20,
        open_position: 100,
        holiday_mode: "always",
      };
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
            <div class="header-icon">🗓️</div>
            <div class="header-title">
              <h1>DomoLink-Planification</h1>
              <p>Moteur d'automatisation temporelle & gestion bioclimatique des volets</p>
            </div>
          </div>
          <div class="header-actions">
            <button class="btn btn-clipboard" id="btn-copy-card">📋 Créer carte Lovelace</button>
            <button class="btn btn-primary" id="btn-add-schedule">+ Planification</button>
            <button class="btn btn-primary" id="btn-add-solar">+ Volet Solaire</button>
          </div>
        </div>

        <div class="tabs">
          <div class="tab ${this._activeTab === 'schedules' ? 'active' : ''}" data-tab="schedules">🕒 Planifications (${timeSchedules.length})</div>
          <div class="tab ${this._activeTab === 'solar' ? 'active' : ''}" data-tab="solar">☀️ Volets Solaires (${solarSchedules.length})</div>
          <div class="tab ${this._activeTab === 'history' ? 'active' : ''}" data-tab="history">📜 Historique Audit</div>
          <div class="tab ${this._activeTab === 'settings' ? 'active' : ''}" data-tab="settings">⚙️ Paramètres</div>
        </div>

        <div id="tab-content">
          ${this._renderActiveTabContent(timeSchedules, solarSchedules, sunAzimuth, sunElevation)}
        </div>

        <div class="toast" id="toast"></div>
      `;

      // Event listeners
      this.shadowRoot.querySelector("#btn-copy-card").addEventListener("click", () => this._copyLovelaceCardCode());
      this.shadowRoot.querySelector("#btn-add-schedule").addEventListener("click", () => this._openScheduleModal(null, false));
      this.shadowRoot.querySelector("#btn-add-solar").addEventListener("click", () => this._openScheduleModal(null, true));

      this.shadowRoot.querySelectorAll(".tab").forEach(el => {
        el.addEventListener("click", (e) => {
          this._activeTab = e.currentTarget.dataset.tab;
          this._render();
        });
      });

      this._attachCardActionListeners();
    }

    _renderActiveTabContent(timeSchedules, solarSchedules, sunAzimuth, sunElevation) {
      if (this._activeTab === "schedules") {
        if (timeSchedules.length === 0) {
          return `
            <div style="text-align: center; padding: 48px; background: rgba(30,41,59,0.4); border-radius: 16px;">
              <p style="font-size: 18px; color: #94a3b8;">Aucune planification temporelle active.</p>
              <button class="btn btn-primary" id="btn-empty-add">+ Créer une première règle</button>
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
              <div style="grid-column: 1/-1; text-align: center; padding: 40px; background: rgba(30,41,59,0.4); border-radius: 14px;">
                <p style="color: #94a3b8;">Aucun volet configuré pour le suivi solaire.</p>
                <button class="btn btn-primary" id="btn-solar-empty-add">+ Configurer un volet solaire</button>
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
                          ${item.status}
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
            <button class="btn btn-primary" id="btn-save-settings">Enregistrer les paramètres</button>
          </div>
        `;
      }
      return "";
    }

    _renderScheduleCard(sched) {
      const isEnabled = sched.enabled !== false;
      const nextRun = (this._data.next_runs || {})[sched.id] || "Calcul en cours...";
      const nextRunFormatted = nextRun.includes("T") ? new Date(nextRun).toLocaleString() : nextRun;

      return `
        <div class="card" data-id="${sched.id}">
          <div>
            <div class="card-header">
              <h3 class="card-title">${sched.name}</h3>
              <label class="switch">
                <input type="checkbox" class="toggle-schedule" ${isEnabled ? "checked" : ""}>
                <span class="slider"></span>
              </label>
            </div>
            <div class="card-details">
              <div><span class="label">Déclencheur :</span> ${sched.trigger_type === 'time' ? `Heure fixe (${sched.time})` : sched.trigger_type}</div>
              <div><span class="label">Cible :</span> ${sched.target_type} ➔ <code>${sched.target_value}</code></div>
              <div><span class="label">Prochaine :</span> <strong style="color:#60a5fa;">${nextRunFormatted}</strong></div>
              <div><span class="label">Jours Fériés :</span> ${sched.holiday_mode || 'Actif'}</div>
            </div>
          </div>
          <div class="card-actions">
            <button class="btn-icon trigger-btn" title="Tester maintenant">▶️</button>
            <button class="btn-icon edit-btn" title="Modifier">✏️</button>
            <button class="btn-icon delete delete-btn" title="Supprimer">🗑️</button>
          </div>
        </div>
      `;
    }

    _renderSolarCard(sched) {
      const isEnabled = sched.enabled !== false;
      const state = (this._data.solar_states || {})[sched.id] || {};
      const statusBadge = state.should_shade ? 
        `<span class="badge badge-warning">☀️ Fermé Solaire (${sched.shading_position}%)</span>` :
        `<span class="badge badge-success">🌤️ Ouvert (${sched.open_position}%)</span>`;

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
            <button class="btn-icon trigger-btn" title="Réévaluer">🔄</button>
            <button class="btn-icon edit-btn" title="Modifier">✏️</button>
            <button class="btn-icon delete delete-btn" title="Supprimer">🗑️</button>
          </div>
        </div>
      `;
    }

    _attachCardActionListeners() {
      // Toggles
      this.shadowRoot.querySelectorAll(".toggle-schedule").forEach(toggle => {
        toggle.addEventListener("change", (e) => {
          const card = e.currentTarget.closest(".card");
          const schedId = card.dataset.id;
          this._toggleSchedule(schedId, !e.currentTarget.checked);
        });
      });

      // Actions
      this.shadowRoot.querySelectorAll(".trigger-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const schedId = e.currentTarget.closest(".card").dataset.id;
          this._triggerNow(schedId);
        });
      });

      this.shadowRoot.querySelectorAll(".edit-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const schedId = e.currentTarget.closest(".card").dataset.id;
          const sched = this._data.schedules[schedId];
          if (sched) this._openScheduleModal(sched, sched.trigger_type === "solar_shading");
        });
      });

      this.shadowRoot.querySelectorAll(".delete-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const schedId = e.currentTarget.closest(".card").dataset.id;
          this._deleteSchedule(schedId);
        });
      });

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

    _renderModal() {
      const s = this._editingSchedule;
      if (!s) return;
      const isSolar = s.trigger_type === "solar_shading";

      const modalEl = document.createElement("div");
      modalEl.className = "modal-backdrop";
      modalEl.innerHTML = `
        <div class="modal">
          <h2>${s.id ? "Modifier la règle" : (isSolar ? "Nouveau Volet Solaire" : "Nouvelle Planification")}</h2>
          
          <div class="form-group">
            <label>Nom de la règle</label>
            <input type="text" class="form-control" id="modal-name" value="${s.name || ''}">
          </div>

          ${isSolar ? `
            <div class="form-group">
              <label>Entité du Volet Roulant (cover.*)</label>
              <input type="text" class="form-control" id="modal-cover-id" placeholder="cover.volet_salon" value="${s.cover_entity_id || ''}">
            </div>

            <div class="form-group">
              <label>Exposition de la façade / fenêtre</label>
              <select class="form-control" id="modal-orientation">
                ${COMPASS_OPTIONS.map(opt => `<option value="${opt.val}" ${opt.val === s.orientation ? 'selected' : ''}>${opt.label}</option>`).join("")}
              </select>
            </div>

            <div class="form-group">
              <label>Capteur de Température de référence (sensor.*)</label>
              <input type="text" class="form-control" id="modal-temp-sensor" placeholder="sensor.salon_temperature" value="${s.temperature_sensor_id || ''}">
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
            <div class="form-group">
              <label>Heure de déclenchement</label>
              <input type="time" class="form-control" id="modal-time" value="${s.time || '07:30'}">
            </div>

            <div class="form-group">
              <label>Type de Cible</label>
              <select class="form-control" id="modal-target-type">
                <option value="label" ${s.target_type === 'label' ? 'selected' : ''}>🏷️ Étiquette (Label HA)</option>
                <option value="entity" ${s.target_type === 'entity' ? 'selected' : ''}>💡 Entité(s) spécifique(s)</option>
                <option value="area" ${s.target_type === 'area' ? 'selected' : ''}>🏠 Pièce (Area)</option>
                <option value="script" ${s.target_type === 'script' ? 'selected' : ''}>📜 Script</option>
                <option value="automation" ${s.target_type === 'automation' ? 'selected' : ''}>⚙️ Automatisation</option>
                <option value="scene" ${s.target_type === 'scene' ? 'selected' : ''}>🎬 Scène</option>
              </select>
            </div>

            <div class="form-group">
              <label>Valeur de la Cible (ex: rez_de_chaussee, light.salon)</label>
              <input type="text" class="form-control" id="modal-target-val" placeholder="ex: volets_rdc ou light.cuisine" value="${s.target_value || ''}">
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
            <button class="btn" id="modal-cancel">Annuler</button>
            <button class="btn btn-primary" id="modal-save">Enregistrer</button>
          </div>
        </div>
      `;

      this.shadowRoot.appendChild(modalEl);

      modalEl.querySelector("#modal-cancel").addEventListener("click", () => this._closeModal());
      modalEl.querySelector("#modal-save").addEventListener("click", () => {
        s.name = modalEl.querySelector("#modal-name").value;
        if (isSolar) {
          s.cover_entity_id = modalEl.querySelector("#modal-cover-id").value;
          s.orientation = modalEl.querySelector("#modal-orientation").value;
          s.temperature_sensor_id = modalEl.querySelector("#modal-temp-sensor").value;
          s.temperature_threshold = parseFloat(modalEl.querySelector("#modal-temp-thresh").value);
          s.shading_position = parseInt(modalEl.querySelector("#modal-pos-shading").value, 10);
          s.open_position = parseInt(modalEl.querySelector("#modal-pos-open").value, 10);
        } else {
          s.time = modalEl.querySelector("#modal-time").value;
          s.target_type = modalEl.querySelector("#modal-target-type").value;
          s.target_value = modalEl.querySelector("#modal-target-val").value;
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
          <div class="title">🗓️ ${this._config.title || "DomoLink-Planification"}</div>
          <p style="margin:0; font-size: 13px; color: #94a3b8;">
            Moteur d'automatisation & suivi solaire actif.
          </p>
          <a href="/domolink-planification" class="link-btn">👉 Ouvrir le panneau de planification</a>
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

  console.info(
    `%c DOMOLINK-PLANIFICATION %c v1.0.0 chargé avec succès `,
    "background: #3b82f6; color: #fff; font-weight: bold; border-radius: 4px 0 0 4px;",
    "background: #1e293b; color: #60a5fa; border-radius: 0 4px 4px 0;"
  );
})();
