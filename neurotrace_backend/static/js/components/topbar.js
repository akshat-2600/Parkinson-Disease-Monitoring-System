/* ============================================================
   js/components/topbar.js — Top navigation bar
   ============================================================ */

const Topbar = (() => {

  const PAGE_TITLES = {
    dashboard:       'Dashboard',
    realtime:        'Real-Time Predict',
    history:         'History',
    explanation:     'Explainability',
    recommendations: 'Recommendations',
  };

  function render() {
    document.getElementById('topbar-root').innerHTML = `
      <header class="topbar">
        <div class="topbar-left">
          <button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="Open menu">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="3" y1="6" x2="21" y2="6"/>
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
          <span class="topbar-title" id="topbarTitle">Dashboard</span>
          <span class="topbar-breadcrumb" id="topbarPatient">PT-001</span>
        </div>
        <div class="topbar-right">
          <div class="realtime-indicator">
            <div class="pulse-dot"></div>
            LIVE
          </div>
          <button class="topbar-btn" data-tooltip="Notifications" id="notifBtn" aria-label="Notifications">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
            <span class="dot" id="notifDot" style="display:none"></span>
          </button>
          <button class="topbar-btn" data-tooltip="Refresh data" id="refreshBtn" aria-label="Refresh">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
            </svg>
          </button>
        </div>
      </header>`;

    _bindEvents();
  }

  function _bindEvents() {
    document.getElementById('mobileMenuBtn')?.addEventListener('click', () => Sidebar.open());
    document.getElementById('refreshBtn')?.addEventListener('click', () => Router.refresh());
  }

  function setPage(page) {
    Helpers.setText('topbarTitle', PAGE_TITLES[page] || page);
  }

  function setPatient(pid) {
    Helpers.setText('topbarPatient', pid);
  }

  function setNotification(hasAlert) {
    const dot = document.getElementById('notifDot');
    if (dot) dot.style.display = hasAlert ? '' : 'none';
  }

  return { render, setPage, setPatient, setNotification };
})();
