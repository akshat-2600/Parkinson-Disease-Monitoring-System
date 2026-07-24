/* ============================================================
   static/js/pages/dashboard.js
   ============================================================ */

const PageDashboard = (() => {
  const ROOT = 'page-dashboard';

  /* ── HTML template ────────────────────────────────── */
  function _html() {
    return `
      <div class="page-header">
        <div>
          <div class="page-title">Patient Overview</div>
          <div class="page-subtitle">Parkinson's monitoring — run a prediction to populate data</div>
        </div>
        <div class="page-actions">
          <button class="btn btn-ghost" id="dashRefreshBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.95"/></svg>
            Refresh
          </button>
          <button class="btn btn-primary" id="dashPredictBtn">⚡ Run Prediction</button>
        </div>
      </div>

      <div id="dashboardError"></div>

      <!-- Loading skeleton -->
      <div id="dashboardLoading" style="display:none">${Skeletons.dashboardSkeleton()}</div>

      <!-- Empty state — shown when patient has no predictions yet -->
      <div id="dashboardEmpty">
        <div class="card" style="text-align:center;padding:60px 24px;margin-bottom:20px">
          <div style="font-size:56px;margin-bottom:16px;opacity:0.4">🧠</div>
          <div style="font-family:var(--font-display);font-size:20px;font-weight:700;margin-bottom:8px">
            No prediction data yet
          </div>
          <div style="font-size:14px;color:var(--text-2);margin-bottom:24px;max-width:400px;margin-left:auto;margin-right:auto">
            Upload patient data and run a prediction to populate the dashboard with
            severity scores, alerts, model contributions and trend charts.
          </div>
          <button class="btn btn-primary" id="dashEmptyPredictBtn" style="margin:auto">
            ⚡ Run First Prediction
          </button>
        </div>

        <!-- Profile card still shown even without predictions -->
        <div class="patient-card section-gap" id="patientCard" style="display:none">
          <div class="patient-avatar" id="patientAvatar">—</div>
          <div class="patient-info">
            <div class="patient-name" id="patientName">—</div>
            <div class="patient-id"   id="patientIdLabel">—</div>
            <div class="patient-meta">
              <span class="meta-tag" id="patientAge">Age: —</span>
              <span class="meta-tag" id="patientGender">Gender: —</span>
              <span class="meta-tag" id="patientDiagnosis">—</span>
              <span class="meta-tag" id="patientOnset">Onset: —</span>
            </div>
          </div>
          <div class="patient-status">
            <span class="status-badge status-stable">🟢 No predictions yet</span>
            <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-3)" id="lastUpdated">—</span>
          </div>
        </div>
      </div>

      <!-- Real data — shown after first prediction -->
      <div id="dashboardData" style="display:none">

        <!-- Patient summary card -->
        <div class="patient-card section-gap">
          <div class="patient-avatar" id="patientAvatarFull">—</div>
          <div class="patient-info">
            <div class="patient-name" id="patientNameFull">—</div>
            <div class="patient-id"   id="patientIdFull">—</div>
            <div class="patient-meta">
              <span class="meta-tag" id="patientAgeFull">Age: —</span>
              <span class="meta-tag" id="patientGenderFull">Gender: —</span>
              <span class="meta-tag" id="patientDiagnosisFull">—</span>
              <span class="meta-tag" id="patientOnsetFull">Onset: —</span>
            </div>
          </div>
          <div class="patient-status">
            <span class="status-badge" id="patientStatusBadge">—</span>
            <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-3)" id="lastUpdatedFull">—</span>
          </div>
        </div>

        <!-- Stat cards -->
        <div class="grid-4 section-gap">
          <div class="stat-card card-glow-cyan">
            <div class="stat-label" data-tooltip="Overall severity 0–100">Severity Score</div>
            <div class="stat-value text-cyan" id="severityScore">—</div>
            <div class="stat-sub"><span id="severityStage">Stage: —</span><span class="stat-change neutral" id="severityChange">—</span></div>
          </div>
          <div class="stat-card card-glow-violet">
            <div class="stat-label" data-tooltip="UPDRS motor score">UPDRS Score</div>
            <div class="stat-value text-violet" id="updrsScore">—</div>
            <div class="stat-sub"><span>Total motor</span></div>
          </div>
          <div class="stat-card card-glow-green">
            <div class="stat-label">Fusion Confidence</div>
            <div class="stat-value text-green" id="fusionConf">—</div>
            <div class="stat-sub"><span>Model consensus</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Active Alerts</div>
            <div class="stat-value text-amber" id="alertCount">—</div>
            <div class="stat-sub"><span>Open flags</span></div>
          </div>
        </div>

        <!-- Gauge + Modality grid -->
        <div class="grid-2 section-gap">
          <div class="card card-glow-cyan">
            <div class="card-header">
              <span class="card-title">Severity Gauge</span>
              <div class="card-icon" style="background:var(--cyan-dim)">📊</div>
            </div>
            <div id="gaugeContainer"></div>
          </div>
          <div class="card card-glow-violet">
            <div class="card-header">
              <span class="card-title">Model Contributions</span>
              <div class="card-icon" style="background:var(--violet-dim)">🔬</div>
            </div>
            <div class="modality-grid" id="modalityGrid"></div>
          </div>
        </div>

        <!-- Progression trend chart -->
        <div class="card card-glow-cyan section-gap">
          <div class="card-header">
            <span class="card-title">Progression Trend</span>
            <span class="stat-change neutral" style="font-size:11px" id="trendPeriod">Last prediction</span>
          </div>
          <div class="chart-wrap" style="height:220px">
            <canvas id="progressionChart"></canvas>
          </div>
        </div>

        <!-- Risk indicators + Alerts -->
        <div class="grid-2">
          <div class="card">
            <div class="card-header">
              <span class="card-title">Risk Indicators</span>
              <div class="card-icon" style="background:var(--red-dim)">⚠️</div>
            </div>
            <div class="risk-list" id="riskList"></div>
          </div>
          <div class="card">
            <div class="card-header">
              <span class="card-title">Active Alerts</span>
              <div class="card-icon" style="background:var(--amber-dim)">🔔</div>
            </div>
            <div class="alert-list" id="alertList"></div>
          </div>
        </div>
      </div>`;
  }

  /* ── Init ─────────────────────────────────────────── */
  function init() {
    document.getElementById(ROOT).innerHTML = _html();
    document.getElementById('gaugeContainer').innerHTML = Gauge.template();

    document.getElementById('dashRefreshBtn')?.addEventListener('click', load);
    document.getElementById('dashPredictBtn')?.addEventListener('click', () => Router.navigate('realtime'));
    document.getElementById('dashEmptyPredictBtn')?.addEventListener('click', () => Router.navigate('realtime'));
  }

  /* ── Load — does NOT show fake data on failure ────── */
  async function load() {
    Helpers.clearError('dashboardError');

    // Don't show skeletons on first load, just the empty state initially
    Helpers.hide('dashboardData');
    Helpers.hide('dashboardLoading');

    // Try fetching real data
    let data = null;
    try {
      Helpers.show('dashboardLoading');
      Helpers.hide('dashboardEmpty');
      const res = await API.getDashboard(App.patientId);
      data = res?.data || null;
    } catch (e) {
      Helpers.hide('dashboardLoading');
      // 401 = not logged in (shouldn't reach here), show empty state
      // 404 = patient not found, show empty state
      // Other errors = show error banner + empty state
      if (!e.message.includes('401') && !e.message.includes('404')) {
        Helpers.showError('dashboardError', `Dashboard error: ${e.message}`);
      }
    }
    Helpers.hide('dashboardLoading');

    // Determine if we have real prediction data to show
    const hasPredictions = data && (
      data.severity != null ||
      (data.alerts && data.alerts.length > 0) ||
      data.fusion_confidence != null
    );

    if (hasPredictions) {
      _renderFull(data);
    } else {
      // Show empty state — also populate profile card if we have basic patient info
      Helpers.show('dashboardEmpty');
      Helpers.hide('dashboardData');
      if (data && (data.name || data.age)) {
        _renderProfileOnly(data);
      }
    }
  }

  /* ── Render profile card only (no predictions yet) ─ */
  function _renderProfileOnly(d) {
    const card = document.getElementById('patientCard');
    if (!card) return;
    card.style.display = '';
    Helpers.setText('patientAvatar',    d.initials || Helpers.initials(d.name || ''));
    Helpers.setText('patientName',      d.name || '—');
    Helpers.setText('patientIdLabel',   `${App.patientId}`);
    Helpers.setText('patientAge',       `Age: ${d.age || '—'}`);
    Helpers.setText('patientGender',    `Gender: ${d.gender || '—'}`);
    Helpers.setText('patientDiagnosis',  d.diagnosis || '—');
    Helpers.setText('patientOnset',     `Onset: ${d.onset || '—'}`);
  }

  /* ── Render full dashboard with prediction data ───── */
  function _renderFull(d) {
    Helpers.hide('dashboardEmpty');
    Helpers.show('dashboardData');

    // Patient info
    Helpers.setText('patientAvatarFull', d.initials || Helpers.initials(d.name || ''));
    Helpers.setText('patientNameFull',   d.name || '—');
    Helpers.setText('patientIdFull',     `${App.patientId} · Neurological Unit`);
    Helpers.setText('patientAgeFull',    `Age: ${d.age || '—'}`);
    Helpers.setText('patientGenderFull', `Gender: ${d.gender || '—'}`);
    Helpers.setText('patientDiagnosisFull', d.diagnosis || '—');
    Helpers.setText('patientOnsetFull',  `Onset: ${d.onset || '—'}`);
    Helpers.setText('lastUpdatedFull',   `Updated: ${Helpers.timeNow()}`);

    // Status badge
    const sb  = document.getElementById('patientStatusBadge');
    if (sb) {
      const map = {
        stable:   ['🟢 Stable',     'status-stable'],
        warning:  ['🟡 Monitoring', 'status-warning'],
        critical: ['🔴 Critical',   'status-critical'],
      };
      const [label, cls] = map[d.status] || map.stable;
      sb.textContent = label;
      sb.className   = `status-badge ${cls}`;
    }

    // Stats
    Helpers.setText('severityScore',  d.severity ?? '—');
    Helpers.setText('severityStage',  d.stage || '—');
    Helpers.setText('severityChange', d.severity_change != null ? `+${d.severity_change}% MoM` : '—');
    Helpers.setText('updrsScore',     d.updrs ?? '—');
    Helpers.setText('fusionConf',     d.fusion_confidence ? `${Helpers.pct(d.fusion_confidence)}%` : '—');

    const alertCount = (d.alerts || []).length;
    Helpers.setText('alertCount', alertCount);
    Sidebar.setAlertBadge(alertCount);
    Topbar.setNotification(alertCount > 0);

    // Visual components
    Gauge.update(d.severity || 0, d.stage || '—');
    _renderModalities(d.modalities || {});
    _renderProgressionChart(d.severity || 0, d.severity_history);
    _renderRisks(d.risks || []);
    _renderAlerts(d.alerts || []);
  }

  /* ── Also callable externally after realtime predict ─ */
  function renderFromPrediction(predResult) {
    // Convert realtime_predict response into dashboard data shape
    const d = {
      name:              predResult.patient_name,
      age:               predResult.patient_age,
      gender:            predResult.patient_gender,
      diagnosis:         "Parkinson's Disease",
      onset:             predResult.patient_onset,
      severity:          predResult.severity,
      stage:             predResult.stage,
      status:            predResult.severity >= 70 ? 'critical' : predResult.severity >= 40 ? 'warning' : 'stable',
      fusion_confidence: predResult.confidence,
      alerts:            predResult.alerts || [],
      risks:             predResult.risks   || [],
      modalities:        predResult.modality_contributions || {},
    };
    _renderFull(d);
  }

  /* ── Private rendering helpers ─────────────────────── */
  function _renderModalities(modalities) {
    const icons  = { voice:'🎤', clinical:'📋', timeseries:'📈', mri:'🧠', spiral:'🌀', motor:'🤚' };
    const labels = { voice:'Voice', clinical:'Clinical', timeseries:'Time-Series', mri:'MRI', spiral:'Spiral', motor:'Motor' };
    const grid   = document.getElementById('modalityGrid');
    if (!grid) return;

    const entries = Object.entries(modalities).filter(([, v]) => v != null && v > 0);
    if (!entries.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-text">No modality data</div></div>`;
      return;
    }

    grid.innerHTML = entries.slice(0, 6).map(([key, val], i) => {
      const pct   = Helpers.pct(val);
      const color = Helpers.PALETTE[i % Helpers.PALETTE.length];
      return `
        <div class="modality-item" data-tooltip="${labels[key] || key} confidence">
          <div class="modality-icon">${icons[key] || '🔬'}</div>
          <div class="modality-name">${labels[key] || key}</div>
          <div class="modality-score" style="color:${color}">${pct}%</div>
          <div class="modality-bar-wrap">
            <div class="modality-bar" style="width:${pct}%;background:${color}"></div>
          </div>
        </div>`;
    }).join('');
  }

  function _renderProgressionChart(currentSeverity, historyPoints) {
    const ctx = document.getElementById('progressionChart')?.getContext('2d');
    if (!ctx) return;

    let labels, vals;
    if (historyPoints && historyPoints.length > 1) {
      // Use real history data if available
      labels = historyPoints.map(h => h.date || h.label);
      vals   = historyPoints.map(h => h.severity);
    } else {
      // Show just the current prediction as a single point with today's date
      const today = new Date().toLocaleDateString('en', { day:'numeric', month:'short' });
      labels = [today];
      vals   = [currentSeverity];
    }

    Charts.create('progression', ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Severity',
          data:  vals,
          borderColor:     '#00d4ff',
          backgroundColor: Charts.gradientFill(ctx, '00d4ff', 220),
          fill: true, tension: 0.4, pointRadius: 4,
          pointHoverRadius: 6, borderWidth: 2,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: Charts.TOOLTIP },
        scales: {
          x: { ...Charts.SCALE.x },
          y: { ...Charts.SCALE.y, min: 0, max: 100 },
        },
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
      },
    });
  }

  function _renderRisks(risks) {
    const cm = { high: 'var(--red)', medium: 'var(--amber)', low: 'var(--green)', moderate: 'var(--amber)' };
    Helpers.setHTML('riskList', risks.length
      ? risks.map(r => `
          <div class="risk-item">
            <div class="risk-dot" style="background:${cm[r.level] || 'var(--cyan)'}"></div>
            <div class="risk-name">${r.name}</div>
            <div class="risk-level risk-${r.level || 'low'}">${(r.level || 'low').toUpperCase()}</div>
          </div>`).join('')
      : `<div class="empty-state"><div class="empty-icon">✅</div><div class="empty-text">No active risks identified</div></div>`
    );
  }

  function _renderAlerts(alerts) {
    Helpers.setHTML('alertList', alerts.length
      ? alerts.map(a => `
          <div class="alert-item alert-${a.type || 'info'}">
            <div class="alert-header">
              <span class="alert-type">${a.type || 'info'}</span>
              <span class="alert-time">${a.time || ''}</span>
            </div>
            <div class="alert-msg">${a.msg || a.message || ''}</div>
          </div>`).join('')
      : `<div class="empty-state"><div class="empty-icon">🔔</div><div class="empty-text">No active alerts</div></div>`
    );
  }

  return { init, load, renderFromPrediction };
})();