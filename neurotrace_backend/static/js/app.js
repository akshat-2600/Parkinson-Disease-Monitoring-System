/* ============================================================
   static/js/app.js  
   ============================================================ */

const App = (() => {
  // Default to PT-001 so dashboard URL is never /api/fusion/dashboard/
  let _patientId   = 'PT-001';
  let _currentPage = 'dashboard';

  function setPatient(pid) {
    if (!pid) return;  // never set to empty string
    _patientId = pid;
    Topbar.setPatient(pid);
    const sel = document.getElementById('patientSelector');
    if (sel && sel.value !== pid) {
      let opt = sel.querySelector(`option[value="${pid}"]`);
      if (!opt) { opt = new Option(pid, pid); sel.add(opt); }
      sel.value = pid;
    }
  }

  return {
    get patientId()   { return _patientId; },
    get currentPage() { return _currentPage; },
    set currentPage(v){ _currentPage = v; },
    setPatient,
  };
})();

const Router = (() => {
  const PAGES = {
    dashboard:       PageDashboard,
    explanation:     PageExplanation,
    recommendations: PageRecommendations,
    history:         PageHistory,
    realtime:        PageRealtime,
    progression:     PageProgression,
  };

  function navigate(page) {
    if (!PAGES[page]) return;

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`page-${page}`);
    if (!target) return;
    target.classList.add('active');

    if (!target.dataset.inited) {
      PAGES[page].init();
      target.dataset.inited = '1';
    }
    // if (page === 'progression' && typeof PageProgression !== 'undefined') {
    //   PageProgression.load();
    // }

    Sidebar.setActive(page);
    Topbar.setPage(page);
    App.currentPage = page;
    PAGES[page].load();
  }

  function refresh() {
    if (PAGES[App.currentPage]) PAGES[App.currentPage].load();
  }

  return { navigate, refresh };
})();

document.addEventListener('DOMContentLoaded', () => {
  Charts.applyDefaults();

  function revealApp() {
    const main    = document.getElementById('main-shell');
    const sidebar = document.getElementById('sidebar-root');
    if (main)    main.style.display    = '';
    if (sidebar) sidebar.style.display = '';
  }

  const _origHide = AuthUI.hideAuth.bind(AuthUI);
  AuthUI.hideAuth = function () {
    _origHide();
    revealApp();
  };

  if (Auth.isLoggedIn()) {
    // Set patient ID from stored session BEFORE any API calls fire
    const uid = Auth.getPatientUid();
    if (uid) App.setPatient(uid);

    revealApp();
    Sidebar.render();
    Topbar.render();

    const role = Auth.getRole();
    if (role === 'doctor') {
      DoctorDashboard.init();
    } else {
      PatientDashboard.init();
    }
  } else {
    AuthUI.showLogin();
  }
});