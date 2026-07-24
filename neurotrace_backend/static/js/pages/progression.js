/* ============================================================
   static/js/pages/progression.js
   NEW PAGE — Personalized Progression & Forecasting
   Satisfies:
     - Objective 3: Personalized Progression Modeling
     - Objective 4: Holistic PD Severity & Progression Prediction
     - Module 3: Explainable Severity and Progression
     - Module 4: Patient-Specific Adaptation
   ============================================================ */

   const PageProgression = (() => {
    const ROOT = 'page-progression';
  
    function _html() {
      return `
        <div class="page-header">
          <div>
            <div class="page-title">Progression Forecast</div>
            <div class="page-subtitle">
              Patient-specific AI modeling — personalized severity prediction & future trajectory
            </div>
          </div>
          <button class="btn btn-ghost" id="progRefreshBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
            </svg>
            Refresh
          </button>
        </div>
  
        <div id="progressionError"></div>
  
        <!-- Empty state -->
        <div id="progressionEmpty">
          <div class="card" style="text-align:center;padding:60px 24px">
            <div style="font-size:56px;margin-bottom:16px;opacity:0.4">🔮</div>
            <div style="font-family:var(--font-display);font-size:18px;font-weight:700;
                        margin-bottom:8px">No forecast data yet</div>
            <div style="font-size:13px;color:var(--text-2);max-width:400px;
                        margin:auto;margin-bottom:20px">
              The personalized forecasting model needs at least
              <strong>2 predictions</strong> to estimate your progression trajectory.
              Run more predictions over time to unlock this feature.
            </div>
            <button class="btn btn-primary" onclick="Router.navigate('realtime')"
                    style="margin:auto">
              ⚡ Run Prediction
            </button>
          </div>
        </div>
  
        <!-- Data panels -->
        <div id="progressionData" style="display:none">
  
          <!-- Baseline + Adaptation Status -->
          <div class="grid-4 section-gap" id="baselineCards"></div>
  
          <!-- Forecast chart -->
          <div class="card card-glow-cyan section-gap">
            <div class="card-header">
              <span class="card-title">90-Day Severity Forecast</span>
              <div style="display:flex;align-items:center;gap:8px">
                <span id="forecastModelBadge"
                      style="font-size:10px;font-family:var(--font-mono);
                             padding:3px 8px;border-radius:99px;
                             background:var(--cyan-dim);color:var(--cyan)">—</span>
                <span id="forecastR2"
                      style="font-size:10px;font-family:var(--font-mono);color:var(--text-3)">—</span>
              </div>
            </div>
            <div class="chart-wrap" style="height:280px">
              <canvas id="forecastChart"></canvas>
            </div>
            <div id="forecastInterpretation"
                 style="font-size:13px;color:var(--text-2);line-height:1.7;
                        margin-top:12px;padding:12px;background:var(--glass);
                        border:1px solid var(--glass-border);border-radius:var(--radius-sm)">
            </div>
          </div>
  
          <!-- Forecast table -->
          <div class="card section-gap">
            <div class="card-header">
              <span class="card-title">Predicted Severity Timeline</span>
              <div class="card-icon" style="background:var(--violet-dim)">📅</div>
            </div>
            <div id="forecastTable"></div>
          </div>
  
          <!-- LIME Explainability -->
          <div class="grid-2 section-gap">
            <div class="card card-glow-violet">
              <div class="card-header">
                <span class="card-title">LIME — Clinical Explanation</span>
                <div class="card-icon" style="background:var(--violet-dim)">🔬</div>
              </div>
              <div id="limeClinical">
                <div class="loading-overlay"><div class="spinner"></div> Loading…</div>
              </div>
            </div>
            <div class="card card-glow-green">
              <div class="card-header">
                <span class="card-title">LIME — Voice Explanation</span>
                <div class="card-icon" style="background:var(--green-dim)">🎤</div>
              </div>
              <div id="limeVoice">
                <div class="loading-overlay"><div class="spinner"></div> Loading…</div>
              </div>
            </div>
          </div>
        </div>`;
    }
  
    function init() {
      const el = document.getElementById(ROOT);
      if (!el) return;
      el.innerHTML = _html();
      document.getElementById('progRefreshBtn')?.addEventListener('click', load);
    }
  
    async function load() {
      Helpers.clearError('progressionError');
      Helpers.hide('progressionData');
      Helpers.hide('progressionEmpty');
  
      const uid = App.patientId;
      if (!uid) { Helpers.show('progressionEmpty'); return; }
  
      let data = null;
      try {
        const res = await API._request('GET', `/progression/summary/${uid}`);
        data = res?.data || null;
      } catch (e) {
        if (!e.message.includes('401') && !e.message.includes('404')) {
          Helpers.showError('progressionError', `Error: ${e.message}`);
        }
      }
  
      if (!data || !data.forecast?.can_forecast) {
        Helpers.show('progressionEmpty');
        return;
      }
  
      Helpers.show('progressionData');
      _renderBaseline(data.baseline);
      _renderForecast(data.forecast);
      _loadLime(uid);
    }
  
    function _renderBaseline(b) {
      if (!b || !b.has_baseline) {
        Helpers.setHTML('baselineCards', '');
        return;
      }
  
      const statusColors = {
        stable:                  'var(--green)',
        improvement:             'var(--cyan)',
        mild_deterioration:      'var(--amber)',
        significant_deterioration:'var(--red)',
      };
      const statusLabels = {
        stable:                  '✅ Stable',
        improvement:             '📉 Improving',
        mild_deterioration:      '📈 Mild Worsening',
        significant_deterioration:'⚠️ Significant Worsening',
      };
      const col   = statusColors[b.adaptation_status] || 'var(--cyan)';
      const label = statusLabels[b.adaptation_status] || b.adaptation_status;
      const sign  = b.absolute_change > 0 ? '+' : '';
  
      Helpers.setHTML('baselineCards', `
        <div class="stat-card card-glow-cyan">
          <div class="stat-label">Personal Baseline</div>
          <div class="stat-value text-cyan">${b.baseline_severity ?? '—'}</div>
          <div class="stat-sub">Initial severity (first readings)</div>
        </div>
        <div class="stat-card card-glow-violet">
          <div class="stat-label">Current Severity</div>
          <div class="stat-value text-violet">${b.latest_severity ?? '—'}</div>
          <div class="stat-sub">Latest measurement</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Change from Baseline</div>
          <div class="stat-value" style="color:${col}">
            ${sign}${b.absolute_change ?? '—'}
          </div>
          <div class="stat-sub">${sign}${b.percent_change ?? '—'}% vs personal baseline</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Adaptation Status</div>
          <div class="stat-value" style="color:${col};font-size:14px;line-height:1.4">
            ${label}
          </div>
          <div class="stat-sub">Based on ${b.n_predictions_used} readings</div>
        </div>`);
    }
  
    function _renderForecast(f) {
      if (!f.can_forecast) return;
  
      // Model badge
      Helpers.setText('forecastModelBadge',
        f.model === 'polynomial' ? 'Polynomial Regression' : 'Linear Regression');
      Helpers.setText('forecastR2', `R² = ${f.r_squared}`);
      Helpers.setHTML('forecastInterpretation',
        `<strong>${f.trend_label}</strong> — ${f.interpretation}`);
  
      // ── Build chart with history + fitted curve + forecast ────
      const ctx = document.getElementById('forecastChart')?.getContext('2d');
      if (!ctx) return;
  
      const histLabels  = f.history_labels || [];
      const histVals    = f.history_values || [];
      const fittedVals  = f.fitted_curve   || [];
      const forecastPts = f.forecast_points || [];
  
      // Forecast labels continue after history
      const fcastLabels = forecastPts.map(p => p.date);
      const fcastVals   = forecastPts.map(p => p.predicted_sev);
      const ciHigh      = forecastPts.map(p => p.ci_high);
      const ciLow       = forecastPts.map(p => p.ci_low);
  
      // Pad history arrays to join smoothly with forecast
      const histPad     = histVals.map(() => null);
      const allLabels   = [...histLabels, ...fcastLabels];
  
      Charts.create('forecast', ctx, {
        type: 'line',
        data: {
          labels: allLabels,
          datasets: [
            {
              label:       'Actual Severity',
              data:        [...histVals, ...histPad.slice(0, fcastVals.length)],
              borderColor: '#00d4ff',
              backgroundColor: Charts.gradientFill(ctx, '00d4ff', 220),
              fill:        true, tension: 0.3, borderWidth: 2,
              pointRadius: 5, pointHoverRadius: 7,
            },
            {
              label:       'Model Fit',
              data:        [...fittedVals, ...histPad.slice(0, fcastVals.length)],
              borderColor: 'rgba(0,212,255,0.4)',
              borderDash:  [4, 4],
              fill:        false, tension: 0.3, borderWidth: 1,
              pointRadius: 0,
            },
            {
              label:       '90-Day Forecast',
              data:        [...Array(histVals.length).fill(null), ...fcastVals],
              borderColor: '#ff6b9d',
              fill:        false, tension: 0.4, borderWidth: 2,
              borderDash:  [6, 3],
              pointRadius: 4, pointStyle: 'triangle',
            },
            {
              label:       'Upper CI',
              data:        [...Array(histVals.length).fill(null), ...ciHigh],
              borderColor: 'rgba(255,107,157,0.2)',
              backgroundColor: 'rgba(255,107,157,0.08)',
              fill:        '+1', tension: 0.4, borderWidth: 1,
              pointRadius: 0,
            },
            {
              label:       'Lower CI',
              data:        [...Array(histVals.length).fill(null), ...ciLow],
              borderColor: 'rgba(255,107,157,0.2)',
              fill:        false, tension: 0.4, borderWidth: 1,
              pointRadius: 0,
            },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { boxWidth: 10, padding: 12, color: '#8892b0',
                        filter: item => !['Upper CI','Lower CI','Model Fit'].includes(item.text) }
            },
            tooltip: Charts.TOOLTIP,
          },
          scales: {
            x: { ...Charts.SCALE.x, ticks: { maxTicksLimit: 10 } },
            y: { ...Charts.SCALE.y, min: 0, max: 100 },
          },
        },
      });
  
      // ── Forecast table ────────────────────────────────────────
      const stageColors = {
        'Stage 0': 'var(--green)',   'Stage I':   'var(--green)',
        'Stage II': 'var(--cyan)',   'Stage III': 'var(--amber)',
        'Stage IV': 'var(--red)',    'Stage V':   'var(--red)',
      };
      Helpers.setHTML('forecastTable', forecastPts.length ? `
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="border-bottom:1px solid var(--glass-border);color:var(--text-3);
                       font-family:var(--font-mono);font-size:11px;text-transform:uppercase">
              <th style="padding:10px 12px;text-align:left">Date</th>
              <th style="padding:10px 12px;text-align:center">Days Ahead</th>
              <th style="padding:10px 12px;text-align:center">Predicted Severity</th>
              <th style="padding:10px 12px;text-align:center">95% CI</th>
              <th style="padding:10px 12px;text-align:left">Stage</th>
            </tr>
          </thead>
          <tbody>
            ${forecastPts.map(p => `
              <tr style="border-bottom:1px solid var(--glass-border)">
                <td style="padding:10px 12px;font-weight:500">${p.date}</td>
                <td style="padding:10px 12px;text-align:center;
                           font-family:var(--font-mono)">+${p.days_ahead}d</td>
                <td style="padding:10px 12px;text-align:center;
                           font-family:var(--font-display);font-weight:700;font-size:16px;
                           color:var(--cyan)">${p.predicted_sev}</td>
                <td style="padding:10px 12px;text-align:center;
                           font-family:var(--font-mono);font-size:11px;color:var(--text-3)">
                  ${p.ci_low} – ${p.ci_high}
                </td>
                <td style="padding:10px 12px">
                  <span style="color:${stageColors[p.stage]||'var(--text-2)'}">
                    ${p.stage}
                  </span>
                </td>
              </tr>`).join('')}
          </tbody>
        </table>` :
        `<div class="empty-state"><div class="empty-text">No forecast data</div></div>`
      );
    }
  
    async function _loadLime(uid) {
      // Clinical LIME
      try {
        const res  = await API._request('GET', `/progression/lime/${uid}/clinical`);
        const data = res?.data;
        if (data?.success && data.features?.length > 0) {
          _renderLime('limeClinical', data);
        } else {
          Helpers.setHTML('limeClinical',
            `<div class="empty-state" style="padding:20px">
               <div class="empty-text">No clinical prediction found</div>
               <div class="empty-sub">Run a clinical data prediction first</div>
             </div>`);
        }
      } catch {
        Helpers.setHTML('limeClinical',
          `<div class="empty-state" style="padding:20px">
             <div class="empty-text">Clinical LIME unavailable</div>
           </div>`);
      }
  
      // Voice LIME
      try {
        const res  = await API._request('GET', `/progression/lime/${uid}/voice`);
        const data = res?.data;
        if (data?.success && data.features?.length > 0) {
          _renderLime('limeVoice', data);
        } else {
          Helpers.setHTML('limeVoice',
            `<div class="empty-state" style="padding:20px">
               <div class="empty-text">No voice prediction found</div>
               <div class="empty-sub">Run a voice prediction first</div>
             </div>`);
        }
      } catch {
        Helpers.setHTML('limeVoice',
          `<div class="empty-state" style="padding:20px">
             <div class="empty-text">Voice LIME unavailable</div>
           </div>`);
      }
    }
  
    function _renderLime(containerId, data) {
      const features = data.features || [];
      Helpers.setHTML(containerId, `
        <div style="margin-bottom:12px;font-size:12px;color:var(--text-2);line-height:1.6;
                    padding:10px;background:var(--glass);border-radius:var(--radius-sm)">
          ${data.summary || ''}
        </div>
        ${features.map((f, i) => {
          const pct    = Math.round(Math.abs(f.importance || f.weight || 0) * 100);
          const isPos  = (f.direction || '') === 'positive' || (f.weight || 0) > 0;
          const color  = isPos ? 'var(--red)' : 'var(--green)';
          const icon   = isPos ? '▲' : '▼';
          return `
            <div style="display:flex;align-items:center;gap:8px;padding:6px 0;
                        border-bottom:1px solid var(--glass-border)">
              <span style="color:${color};font-size:11px;width:12px">${icon}</span>
              <div style="flex:1;font-size:12px;overflow:hidden;
                          white-space:nowrap;text-overflow:ellipsis"
                   title="${f.name}">${f.name}</div>
              <div style="width:80px;background:var(--glass-border);
                          border-radius:99px;height:6px;overflow:hidden">
                <div style="width:${Math.min(pct,100)}%;height:100%;
                            background:${color};border-radius:99px"></div>
              </div>
              <span style="font-size:11px;font-family:var(--font-mono);
                           color:${color};width:36px;text-align:right">
                ${pct}%
              </span>
            </div>`;
        }).join('')}
        <div style="font-size:10px;color:var(--text-3);margin-top:8px;
                    font-family:var(--font-mono)">
          ▲ = supports PD diagnosis &nbsp;|&nbsp; ▼ = argues against
        </div>`);
    }
  
    return { init, load };
  })();