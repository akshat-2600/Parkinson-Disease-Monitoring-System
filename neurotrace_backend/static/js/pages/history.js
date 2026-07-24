/* ============================================================
   static/js/pages/history.js — TIMEZONE FIXED
   Change: _render() re-formats UTC labels to browser local time
   All other logic unchanged from history_fixed.js
   ============================================================ */
   const PageHistory = (() => {
    const ROOT = 'page-history';
  
    /* Convert "26 Mar 00:17" (UTC) → local time string using browser timezone */
    function _utcLabelToLocal(label) {
      if (!label || label === '—') return label;
      try {
        // Labels are formatted as "D Mon HH:MM" in UTC by the backend
        // Parse by appending UTC explicitly
        const d = new Date(label + ' UTC');
        if (isNaN(d.getTime())) return label;
        // Format in browser's local timezone
        return d.toLocaleString(undefined, {
          day:    'numeric',
          month:  'short',
          hour:   '2-digit',
          minute: '2-digit',
          hour12: false,
        });
      } catch { return label; }
    }
  
    function _localiseLabels(labels) {
      if (!Array.isArray(labels)) return labels;
      return labels.map(_utcLabelToLocal);
    }
  
    function _html() {
      return `
        <div class="page-header">
          <div>
            <div class="page-title">Historical Tracking</div>
            <div class="page-subtitle">Longitudinal progression analysis & intervention timeline</div>
          </div>
          <button class="btn btn-ghost" id="histRefreshBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
            </svg>
            Refresh
          </button>
        </div>
        <div id="historyError"></div>
        <div id="historyLoading" style="display:none">${Skeletons.historySkeleton()}</div>
  
        <div id="historyEmpty">
          <div class="card" style="text-align:center;padding:60px 24px">
            <div style="font-size:56px;margin-bottom:16px;opacity:0.4">📊</div>
            <div style="font-family:var(--font-display);font-size:18px;font-weight:700;margin-bottom:8px">
              No history available
            </div>
            <div style="font-size:13px;color:var(--text-2);max-width:380px;margin:auto;margin-bottom:20px">
              History charts will appear here as predictions accumulate over time.
            </div>
            <button class="btn btn-primary" onclick="Router.navigate('realtime')" style="margin:auto">
              ⚡ Run First Prediction
            </button>
          </div>
        </div>
  
        <div id="historyData" style="display:none">
          <div class="card card-glow-cyan section-gap">
            <div class="card-header">
              <span class="card-title">Severity Timeline</span>
              <span class="text-muted" style="font-size:11px;font-family:var(--font-mono)"
                    id="histPeriodLabel">—</span>
            </div>
            <div class="chart-wrap" style="height:240px">
              <canvas id="historySeverityChart"></canvas>
            </div>
          </div>
  
          <div class="grid-2 section-gap">
            <div class="card card-glow-violet">
              <div class="card-header"><span class="card-title">UPDRS Scores</span></div>
              <div id="historyUpdrsWrap" class="chart-wrap" style="height:200px">
                <canvas id="historyUpdrsChart"></canvas>
              </div>
            </div>
            <div class="card card-glow-green">
              <div class="card-header"><span class="card-title">Multi-Modality Trends</span></div>
              <div id="historyModalityWrap" class="chart-wrap" style="height:200px">
                <canvas id="historyModalityChart"></canvas>
              </div>
            </div>
          </div>
  
          <div class="card">
            <div class="card-header">
              <span class="card-title">Intervention Timeline</span>
              <div class="card-icon" style="background:var(--cyan-dim)">📋</div>
            </div>
            <div class="history-timeline" id="interventionTimeline"></div>
          </div>
        </div>`;
    }
  
    function init() {
      document.getElementById(ROOT).innerHTML = _html();
      document.getElementById('histRefreshBtn')?.addEventListener('click', load);
    }
  
    async function load() {
      Helpers.clearError('historyError');
      Helpers.hide('historyData');
      let data = null;
      try {
        Helpers.show('historyLoading');
        Helpers.hide('historyEmpty');
        const res = await API.getHistory(App.patientId);
        data = res?.data || null;
      } catch (e) {
        Helpers.hide('historyLoading');
        if (!e.message.includes('401') && !e.message.includes('404')) {
          Helpers.showError('historyError', `Error: ${e.message}`);
        }
      }
      Helpers.hide('historyLoading');
  
      const hasHistory = data && Array.isArray(data.labels) && data.labels.length > 0;
      hasHistory ? _render(data) : Helpers.show('historyEmpty');
    }
  
    function _render(d) {
      Helpers.hide('historyEmpty');
      Helpers.show('historyData');
  
      // ── Convert all UTC labels to local browser timezone ──────
      const labels = _localiseLabels(d.labels || []);
      Helpers.setText('histPeriodLabel',
        `${labels.length} prediction${labels.length !== 1 ? 's' : ''}`);
  
      // ── Severity timeline ──────────────────────────────────────
      _line('historySeverity', 'historySeverityChart', labels, [{
        label: 'Severity', data: d.severity || [],
        borderColor: '#00d4ff',
        backgroundColor: 'rgba(0,212,255,0.08)',
        fill: true, tension: 0.4, borderWidth: 2, pointRadius: 4, pointHoverRadius: 7,
      }], { minY: 0, maxY: 100 });
  
      // ── UPDRS ──────────────────────────────────────────────────
      const hasUpdrs = d.updrs && d.updrs.some(v => v != null);
      if (hasUpdrs) {
        _line('historyUpdrs', 'historyUpdrsChart', labels, [{
          label: 'UPDRS', data: d.updrs,
          borderColor: '#7b5cff', backgroundColor: 'rgba(123,92,255,0.1)',
          fill: true, tension: 0.4, borderWidth: 2, pointRadius: 2,
        }], {});
      } else {
        const wrap = document.getElementById('historyUpdrsWrap');
        if (wrap) wrap.innerHTML =
          `<div class="empty-state" style="padding:40px">
             <div class="empty-text">No UPDRS data yet</div>
             <div class="empty-sub">Requires motor prediction with UPDRS output</div>
           </div>`;
      }
  
      // ── Multi-modality trends — all modalities ─────────────────
      const MODALITY_CFG = [
        { key: 'voice',      label: 'Voice',       color: '#00e5a0', lKey: 'voice_labels'      },
        { key: 'mri',        label: 'MRI',          color: '#ffb547', lKey: 'mri_labels'        },
        { key: 'motor',      label: 'Motor',        color: '#ff6b9d', lKey: 'motor_labels'      },
        { key: 'clinical',   label: 'Clinical',     color: '#7b5cff', lKey: 'clinical_labels'   },
        { key: 'spiral',     label: 'Spiral',       color: '#00d4ff', lKey: 'spiral_labels'     },
        { key: 'timeseries', label: 'Time-Series',  color: '#ffd700', lKey: 'timeseries_labels' },
      ];
  
      const modalityDatasets = [];
      MODALITY_CFG.forEach(cfg => {
        const vals = d[cfg.key];
        if (!vals || !vals.some(v => v != null)) return;
        const rawLabels  = d[cfg.lKey] && d[cfg.lKey].length > 0 ? d[cfg.lKey] : d.labels;
        const localLabels = _localiseLabels(rawLabels);
        modalityDatasets.push({
          label:        cfg.label,
          data:         vals,
          _localLabels: localLabels,
          borderColor:  cfg.color,
          tension:      0.4,
          borderWidth:  1.5,
          pointRadius:  3,
          fill:         false,
        });
      });
  
      if (modalityDatasets.length > 0) {
        const allLabels = modalityDatasets.reduce(
          (acc, ds) => ds._localLabels.length > acc.length ? ds._localLabels : acc,
          labels
        );
        const aligned = modalityDatasets.map(({ _localLabels, ...rest }) => rest);
        _line('historyModality', 'historyModalityChart', allLabels, aligned,
          { minY: 0, maxY: 1, legend: true });
      } else {
        const wrap = document.getElementById('historyModalityWrap');
        if (wrap) wrap.innerHTML =
          `<div class="empty-state" style="padding:40px">
             <div class="empty-text">No modality data yet</div>
             <div class="empty-sub">Run voice, MRI, motor or other predictions to see trends</div>
           </div>`;
      }
  
      // ── Intervention timeline — all modalities ─────────────────
      const ICONS = {
        voice:'🎤', clinical:'📋', mri:'🧠', spiral:'🌀',
        motor:'🤚', timeseries:'📈', fusion:'⚡'
      };
      const interventions = d.interventions || [];
  
      Helpers.setHTML('interventionTimeline', interventions.length
        ? interventions.map(i => {
            // Use ISO date if available for accurate local time, else use label
            const displayDate = i.iso ? _isoToLocal(i.iso) : _utcLabelToLocal(i.date || '—');
            return `
              <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-date">${displayDate}</div>
                <div class="timeline-event">
                  <span style="margin-right:6px">${ICONS[i.modality] || '🔬'}</span>
                  ${i.event}
                  <span style="margin-left:8px;font-size:10px;padding:2px 7px;
                               border-radius:99px;background:var(--glass);color:var(--text-3)">
                    ${i.label || ''}
                  </span>
                </div>
              </div>`;
          }).join('')
        : `<div class="empty-state" style="padding:20px">
             <div class="empty-text">No interventions recorded yet</div>
           </div>`
      );
    }
  
    /* Convert ISO string → local time using browser timezone */
    function _isoToLocal(iso) {
      if (!iso) return '—';
      try {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        return d.toLocaleString(undefined, {
          day:    'numeric',
          month:  'short',
          year:   'numeric',
          hour:   '2-digit',
          minute: '2-digit',
          hour12: true,
        });
      } catch { return iso; }
    }
  
    function _line(key, canvasId, labels, datasets, opts = {}) {
      const ctx = document.getElementById(canvasId)?.getContext('2d');
      if (!ctx) return;
      datasets.forEach(ds => {
        if (ds.fill && !ds.backgroundColor && ds.borderColor) {
          ds.backgroundColor = Charts.gradientFill(
            ctx, ds.borderColor.replace('#', ''), 240);
        }
      });
      Charts.create(key, ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: opts.legend
              ? { position: 'bottom', labels: { boxWidth: 10, padding: 12, color: '#8892b0' } }
              : { display: false },
            tooltip: Charts.TOOLTIP,
          },
          scales: {
            x: { ...Charts.SCALE.x, ticks: { maxTicksLimit: opts.maxX || 10 } },
            y: { ...Charts.SCALE.y, min: opts.minY, max: opts.maxY },
          },
        },
      });
    }
  
    return { init, load };
  })();