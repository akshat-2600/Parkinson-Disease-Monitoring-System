/* ============================================================
   static/js/pages/recommendations.js
   ============================================================ */
const PageRecommendations = (() => {
  const ROOT = 'page-recommendations';
  let _allRecs = [];

  function _html() {
    return `
      <div class="page-header">
        <div>
          <div class="page-title">Recommendations</div>
          <div class="page-subtitle">Personalised AI-driven clinical action plan</div>
        </div>
        <button class="btn btn-ghost" id="recRefreshBtn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.95"/></svg>
          Refresh
        </button>
      </div>
      <div id="recommendationsError"></div>

      <!-- Empty state -->
      <div id="recommendationsEmpty">
        <div class="card" style="text-align:center;padding:60px 24px">
          <div style="font-size:56px;margin-bottom:16px;opacity:0.4">📋</div>
          <div style="font-family:var(--font-display);font-size:18px;font-weight:700;margin-bottom:8px">No recommendations yet</div>
          <div style="font-size:13px;color:var(--text-2);max-width:380px;margin:auto;margin-bottom:20px">
            Recommendations are generated automatically after a prediction is made.
            Severity level determines priority of actions.
          </div>
          <button class="btn btn-primary" onclick="Router.navigate('realtime')" style="margin:auto">
            ⚡ Run Prediction First
          </button>
        </div>
      </div>

      <!-- Data -->
      <div id="recommendationsData" style="display:none">
        <div class="section-tabs" id="recTabs">
          <button class="tab-btn active" data-filter="all">All</button>
          <button class="tab-btn" data-filter="high">🔴 High Priority</button>
          <button class="tab-btn" data-filter="moderate">🟡 Moderate</button>
          <button class="tab-btn" data-filter="preventive">🟢 Preventive</button>
        </div>
        <div id="recLoading" style="display:none">${Skeletons.recommendationsSkeleton()}</div>
        <div class="rec-cards" id="recCards"></div>
      </div>`;
  }

  function init() {
    document.getElementById(ROOT).innerHTML = _html();
    document.getElementById('recRefreshBtn')?.addEventListener('click', load);
    document.getElementById('recTabs')?.addEventListener('click', e => {
      const btn = e.target.closest('.tab-btn'); if (!btn) return;
      document.querySelectorAll('#recTabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _renderFiltered(btn.dataset.filter);
    });
  }

  async function load() {
    Helpers.clearError('recommendationsError');
    Helpers.hide('recommendationsData');

    let recs = null;
    try {
      Helpers.show('recLoading');
      Helpers.hide('recommendationsEmpty');
      const res = await API.getRecommendations(App.patientId);
      recs = Array.isArray(res?.data) ? res.data : (res?.data?.recommendations || null);
    } catch (e) {
      Helpers.hide('recLoading');
      if (!e.message.includes('401') && !e.message.includes('404')) {
        Helpers.showError('recommendationsError', `Error: ${e.message}`);
      }
    }
    Helpers.hide('recLoading');

    if (recs && recs.length > 0) {
      _allRecs = recs;
      Helpers.show('recommendationsData');
      Helpers.hide('recommendationsEmpty');
      _renderFiltered('all');
    } else {
      Helpers.show('recommendationsEmpty');
    }
  }

  /* Call after realtime prediction returns recommendations */
  function renderDirect(recs) {
    if (!recs || !recs.length) return;
    _allRecs = recs;
    Helpers.show('recommendationsData');
    Helpers.hide('recommendationsEmpty');
    _renderFiltered('all');
  }

  function _renderFiltered(filter) {
    const list = filter === 'all' ? _allRecs : _allRecs.filter(r => r.priority === filter);
    const container = document.getElementById('recCards'); if (!container) return;

    if (!list.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">✅</div><div class="empty-text">No ${filter === 'all' ? '' : filter} recommendations</div></div>`;
      return;
    }

    const icons = { high: '🔴', moderate: '🟡', preventive: '🟢' };
    container.innerHTML = list.map(r => {
      const pct = Helpers.pct(r.confidence ?? 0);
      return `
        <div class="rec-card">
          <div class="rec-card-header">
            <div class="rec-title">${r.title}</div>
            <span class="rec-priority priority-${r.priority}">${icons[r.priority] || '⚪'} ${r.priority}</span>
          </div>
          <div class="rec-reasoning">${r.reasoning}</div>
          <div class="rec-footer">
            <div class="rec-confidence">
              Confidence: ${pct}%
              <span class="confidence-bar-wrap"><span class="confidence-bar" style="width:${pct}%"></span></span>
            </div>
            <span class="rec-category-tag">${r.category || 'General'}</span>
          </div>
        </div>`;
    }).join('');
  }

  return { init, load, renderDirect };
})();