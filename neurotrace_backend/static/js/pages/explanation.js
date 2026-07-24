/* ============================================================
   static/js/pages/explanation.js — FIXED
   Changes:
   - Renders MRI heatmap from base64 stored in DB
   - Renders Spiral heatmap from base64 stored in DB
   - Uses _localDateStr for any timestamps shown
   ============================================================ */
   const PageExplanation = (() => {
    const ROOT = 'page-explanation';
  
    function _html() {
      return `
        <div class="page-header">
          <div>
            <div class="page-title">Explainability</div>
            <div class="page-subtitle">AI decision transparency — feature importance & attention maps</div>
          </div>
          <button class="btn btn-ghost" id="explRefreshBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
            </svg>
            Refresh
          </button>
        </div>
        <div id="explanationError"></div>
        <div id="explanationLoading" style="display:none">${Skeletons.explanationSkeleton()}</div>
  
        <!-- Empty state -->
        <div id="explanationEmpty">
          <div class="card" style="text-align:center;padding:60px 24px">
            <div style="font-size:56px;margin-bottom:16px;opacity:0.4">🔍</div>
            <div style="font-family:var(--font-display);font-size:18px;font-weight:700;margin-bottom:8px">
              No explanation data yet
            </div>
            <div style="font-size:13px;color:var(--text-2);max-width:380px;margin:auto;margin-bottom:20px">
              Run a prediction first — explainability analysis will appear here after the AI processes patient data.
            </div>
            <button class="btn btn-primary" onclick="Router.navigate('realtime')" style="margin:auto">
              ⚡ Run Prediction First
            </button>
          </div>
        </div>
  
        <!-- Data -->
        <div id="explanationData" style="display:none">
          <div class="grid-2 section-gap">
            <div class="card card-glow-cyan">
              <div class="card-header">
                <span class="card-title">Feature Importance</span>
                <div class="card-icon" style="background:var(--cyan-dim)">📈</div>
              </div>
              <div class="feature-bars" id="featureBars"></div>
            </div>
            <div class="card card-glow-violet">
              <div class="card-header">
                <span class="card-title">MRI Attention Heatmap</span>
                <div class="card-icon" style="background:var(--violet-dim)">🧠</div>
              </div>
              <div class="heatmap-wrap" id="mriHeatmap">
                <div class="heatmap-placeholder">
                  <div style="font-size:32px;margin-bottom:8px">🧠</div>
                  <div>MRI heatmap available after MRI prediction</div>
                </div>
              </div>
            </div>
          </div>
  
          <div class="grid-2 section-gap">
            <div class="card">
              <div class="card-header">
                <span class="card-title">Spiral Drawing Heatmap</span>
                <div class="card-icon" style="background:var(--green-dim)">🌀</div>
              </div>
              <div class="heatmap-wrap" id="spiralHeatmap">
                <div class="heatmap-placeholder">
                  <div style="font-size:32px;margin-bottom:8px">🌀</div>
                  <div>Spiral heatmap available after spiral prediction</div>
                </div>
              </div>
            </div>
            <div class="card card-glow-green">
              <div class="card-header">
                <span class="card-title">Attention Weights</span>
                <div class="card-icon" style="background:var(--green-dim)">🎯</div>
              </div>
              <div class="chart-wrap" style="height:200px">
                <canvas id="attentionChart"></canvas>
              </div>
            </div>
          </div>
  
          <div class="card card-glow-cyan">
            <div class="card-header">
              <span class="card-title">AI Explanation Summary</span>
              <div class="card-icon" style="background:var(--cyan-dim)">💡</div>
            </div>
            <div class="explanation-summary" id="explanationSummary"></div>
          </div>
        </div>`;
    }
  
    function init() {
      document.getElementById(ROOT).innerHTML = _html();
      document.getElementById('explRefreshBtn')?.addEventListener('click', load);
    }
  
    async function load() {
      Helpers.clearError('explanationError');
      Helpers.hide('explanationData');
  
      let data = null;
      try {
        Helpers.show('explanationLoading');
        Helpers.hide('explanationEmpty');
        const res = await API.getExplanation(App.patientId);
        data = res?.data || null;
      } catch (e) {
        Helpers.hide('explanationLoading');
        if (!e.message.includes('401') && !e.message.includes('404')) {
          Helpers.showError('explanationError', `Error: ${e.message}`);
        }
      }
      Helpers.hide('explanationLoading');
  
      // Render if we have features OR heatmaps
      const hasData = data && (
        (data.features && data.features.length > 0) ||
        data.mri_heatmap_base64 || data.mri_heatmap_url ||
        data.spiral_heatmap_base64 || data.spiral_heatmap_url
      );
  
      if (hasData) {
        _render(data);
      } else {
        Helpers.show('explanationEmpty');
      }
    }
  
    /* Called directly from realtime.js after prediction */
    function renderDirect(explData) {
      if (!explData) return;
      _render(explData);
    }
  
    function _render(d) {
      Helpers.hide('explanationEmpty');
      Helpers.show('explanationData');
  
      // ── Feature importance bars ────────────────────────────────
      const features = d.features || [];
      if (features.length > 0) {
        Helpers.setHTML('featureBars', features.map((f, i) => {
          // Support both {name, importance} and {feature, shap_value}
          const name  = f.name || f.feature || '—';
          const imp   = Math.abs(f.importance ?? f.shap_value ?? f.value ?? 0);
          const pct   = Helpers.pct(imp);
          const color = Helpers.PALETTE[i % Helpers.PALETTE.length];
          return `
            <div class="feature-row">
              <div class="feature-name">${name}</div>
              <div class="feature-bar-wrap">
                <div class="feature-bar" style="width:${pct}%;background:${color}"></div>
              </div>
              <div class="feature-pct">${pct}%</div>
            </div>`;
        }).join(''));
      } else {
        Helpers.setHTML('featureBars',
          `<div class="empty-state" style="padding:20px">
             <div class="empty-text">No feature data available</div>
             <div class="empty-sub">Run a clinical, voice, or motor prediction</div>
           </div>`);
      }
  
      // ── MRI heatmap ───────────────────────────────────────────
      _setHeatmap(
        'mriHeatmap',
        d.mri_heatmap_url,
        d.mri_heatmap_base64,
        '🧠',
        'MRI heatmap not available — run an MRI prediction first'
      );
  
      // ── Spiral heatmap ─────────────────────────────────────────
      _setHeatmap(
        'spiralHeatmap',
        d.spiral_heatmap_url,
        d.spiral_heatmap_base64,
        '🌀',
        'Spiral heatmap not available — run a spiral drawing prediction first'
      );
  
      // ── Attention weights radar ────────────────────────────────
      if (d.attention && d.attention.length > 0) {
        const modLabels = ['Voice','Clinical','Time-Series','MRI','Spiral','Motor','Gait','Tremor'];
        Charts.radar('attention', 'attentionChart',
          modLabels.slice(0, d.attention.length), d.attention, '#00e5a0');
      }
  
      // ── Summary ────────────────────────────────────────────────
      Helpers.setHTML('explanationSummary',
        d.summary || d.explanation_text || 'Explanation generated from model analysis.');
    }
  
    function _setHeatmap(id, url, b64, emoji, placeholder) {
      const el = document.getElementById(id);
      if (!el) return;
  
      if (url) {
        el.innerHTML = `
          <img src="${url}" alt="Heatmap"
               style="max-width:100%;border-radius:var(--radius-sm);display:block"/>`;
      } else if (b64) {
        el.innerHTML = `
          <img src="data:image/png;base64,${b64}" alt="Heatmap"
               style="max-width:100%;border-radius:var(--radius-sm);display:block"
               title="AI attention heatmap — brighter regions indicate higher model focus"/>
          <div style="font-size:10px;color:var(--text-3);text-align:center;margin-top:6px;
                      font-family:var(--font-mono)">
            Grad-CAM attention map
          </div>`;
      } else {
        el.innerHTML = `
          <div class="heatmap-placeholder">
            <div style="font-size:32px;margin-bottom:8px">${emoji}</div>
            <div style="font-size:12px;color:var(--text-3)">${placeholder}</div>
          </div>`;
      }
    }
  
    return { init, load, renderDirect };
  })();