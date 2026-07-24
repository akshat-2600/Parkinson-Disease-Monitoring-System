/* ============================================================
   js/components/sidebar.js — Sidebar HTML injection & events
   ============================================================ */

const Sidebar = (() => {

  const NAV_ITEMS = [
    { page: 'dashboard',       label: 'Dashboard',        icon: 'grid',       section: 'Monitoring', badge: true  },
    { page: 'realtime',        label: 'Real-Time Predict',icon: 'bolt',       section: null,         badge: false },
    { page: 'history',         label: 'History',          icon: 'wave',       section: null,         badge: false },
    { page: 'explanation',     label: 'Explainability',   icon: 'search',     section: 'Analysis',   badge: false },
    { page: 'recommendations', label: 'Recommendations',  icon: 'check',      section: null,         badge: false },
    { page: 'progression',     label: 'Progression',      icon: 'trend',         section: null,         badge: false },
  ];

  const ICONS = {
    grid:   `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>`,
    bolt:   `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    wave:   `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
    search: `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
    check:  `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
    trend: `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="14 7 21 7 21 14"/></svg>`,
  };

  function navItemHTML(item) {
    const badge = item.badge
      ? `<span class="nav-badge" id="alertBadge" style="display:none">0</span>`
      : '';
    return `
      <a class="nav-item" data-page="${item.page}" id="nav-${item.page}">
        ${ICONS[item.icon]}
        ${item.label}
        ${badge}
      </a>`;
  }

  function render() {
    let html = `
      <aside class="sidebar" id="sidebar">
        <div class="sidebar-logo">
          <div class="logo-mark">
            <div class="logo-icon">🧠</div>
            <div>
              <div class="logo-text">NeuroTrace</div>
              <div class="logo-sub">Parkinson's AI Platform</div>
            </div>
          </div>
        </div>

        <div class="patient-select-wrap">
          <div class="patient-select-label">Active Patient</div>
          <select class="patient-select" id="patientSelector">
            <option value="PT-001">PT-001 — James Harrington</option>
            <option value="PT-002">PT-002 — Maria Chen</option>
            <option value="PT-003">PT-003 — Robert Okafor</option>
            <option value="PT-004">PT-004 — Susan Patel</option>
          </select>
        </div>

        <nav class="sidebar-nav">`;

    let lastSection = null;
    for (const item of NAV_ITEMS) {
      if (item.section && item.section !== lastSection) {
        html += `<div class="nav-section-label">${item.section}</div>`;
        lastSection = item.section;
      }
      html += navItemHTML(item);
    }

    html += `
        </nav>
        <div class="sidebar-footer">
          <div class="theme-toggle">
            <span>Dark Mode</span>
            <div class="toggle-switch on" id="themeToggle"></div>
          </div>
        </div>
      </aside>`;

    document.getElementById('sidebar-root').innerHTML = html;
    _bindEvents();
  }

  function _bindEvents() {
    // Navigation items
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', () => {
        Router.navigate(el.dataset.page);
        close();
      });
    });

    // Patient selector
    document.getElementById('patientSelector').addEventListener('change', function () {
      App.setPatient(this.value);
    });

    // Theme toggle
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);

    // Mobile overlay
    document.getElementById('sidebarOverlay').addEventListener('click', close);
  }

  function setActive(page) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`nav-${page}`);
    if (target) target.classList.add('active');
  }

  function setAlertBadge(count) {
    const badge = document.getElementById('alertBadge');
    if (!badge) return;
    if (count > 0) { badge.style.display = ''; badge.textContent = count; }
    else           { badge.style.display = 'none'; }
  }

  function open()  {
    document.getElementById('sidebar')?.classList.add('open');
    document.getElementById('sidebarOverlay')?.classList.add('active');
  }

  function close() {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebarOverlay')?.classList.remove('active');
  }

  function toggleTheme() {
    const html   = document.documentElement;
    const toggle = document.getElementById('themeToggle');
    if (html.dataset.theme === 'dark') {
      html.dataset.theme = 'light';
      toggle.classList.remove('on');
    } else {
      html.dataset.theme = 'dark';
      toggle.classList.add('on');
    }
  }

  return { render, setActive, setAlertBadge, open, close };
})();
