/* ============================================================
   static/js/auth/doctor_dashboard.js  
   ============================================================ */

const DoctorDashboard = (() => {
  let _patients = [];

  function init() {
    Sidebar.render();
    Topbar.render();
    _patchTopbar();
    Router.navigate('dashboard');
    _renderDoctorDashboard();
    _loadAll();
  }

  function _patchTopbar() {
    const right = document.querySelector('.topbar-right');
    if (!right) return;
    const user = Auth.getUser();

    const badge = document.createElement('span');
    badge.className   = 'role-badge doctor';
    badge.textContent = '👨‍⚕️ Doctor';
    right.prepend(badge);

    const logoutBtn = document.createElement('button');
    logoutBtn.className = 'topbar-btn';
    logoutBtn.setAttribute('data-tooltip', 'Sign out');
    logoutBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`;
    logoutBtn.addEventListener('click', () => Auth.logout());
    right.appendChild(logoutBtn);

    Helpers.setText('topbarPatient', `Dr. ${user?.last_name || user?.first_name || 'Doctor'}`);
  }

  function _renderDoctorDashboard() {
    const user = Auth.getUser();
    const root = document.getElementById('page-dashboard');
    if (!root) return;
    root.dataset.inited = '1';

    root.innerHTML = `
      <div class="doctor-header">
        <div class="doctor-info">
          <div class="doctor-avatar-wrap">
            <div class="doctor-avatar">${_ini(user)}</div>
            <div class="doctor-online-dot"></div>
          </div>
          <div class="doctor-name-wrap">
            <div class="name">Dr. ${user?.first_name || ''} ${user?.last_name || ''}</div>
            <div class="role-tag">Neurologist · NeuroTrace Platform</div>
          </div>
        </div>
        <div class="doctor-stats">
          <div class="doc-stat"><div class="val" id="docStatPatients">—</div><div class="lbl">Patients</div></div>
          <div class="doc-stat"><div class="val text-amber" id="docStatActive">—</div><div class="lbl">Monitored</div></div>
          <div class="doc-stat"><div class="val text-red" id="docStatCritical">—</div><div class="lbl">Critical</div></div>
        </div>
      </div>

      <div class="table-search-bar section-gap">
        <div class="search-icon-wrap" style="flex:1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input class="table-search" id="patientSearch" placeholder="Search by name or patient ID…" />
        </div>
        <button class="btn btn-ghost" onclick="DoctorDashboard.filterSeverity('all',this)">All</button>
        <button class="btn btn-ghost" onclick="DoctorDashboard.filterSeverity('critical',this)">🔴 Critical</button>
        <button class="btn btn-ghost" onclick="DoctorDashboard.filterSeverity('moderate',this)">🟡 Moderate</button>
        <button class="btn btn-ghost" onclick="DoctorDashboard.filterSeverity('stable',this)">🟢 Stable</button>
      </div>

      <div class="card card-glow-cyan section-gap">
        <div class="card-header">
          <span class="card-title">All Patients</span>
          <span class="text-mono" style="font-size:11px;color:var(--text-3)" id="patientCount">Loading…</span>
        </div>
        <div class="patient-table-wrap">
          <table class="patient-table">
            <thead><tr><th>Patient</th><th>Age</th><th>Gender</th><th>Diagnosis</th><th>Severity</th><th>Status</th><th>Last Prediction</th><th></th></tr></thead>
            <tbody id="patientTableBody">
              <tr><td colspan="8" style="text-align:center;padding:40px"><div class="spinner" style="margin:auto"></div></td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="grid-4">
        <div class="stat-card card-glow-cyan"><div class="stat-label">Total Patients</div><div class="stat-value text-cyan" id="docStatPatients2">—</div></div>
        <div class="stat-card card-glow-violet"><div class="stat-label">Avg Severity</div><div class="stat-value text-violet" id="docAvgSeverity">—</div></div>
        <div class="stat-card"><div class="stat-label">Stable Patients</div><div class="stat-value text-green" id="docStableCount">—</div></div>
        <div class="stat-card"><div class="stat-label">Critical Alerts</div><div class="stat-value text-red" id="docCriticalCount">—</div></div>
      </div>`;

    document.getElementById('patientSearch')?.addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      _renderTable(_patients.filter(p =>
        (p.name || '').toLowerCase().includes(q) ||
        (p.patient_uid || '').toLowerCase().includes(q)
      ));
    });
  }

  async function _loadAll() {
    try {
      // FIXED: No token argument — client.js reads it internally
      const res = await API.listPatients(1, 200);
      _patients  = res.data?.patients || [];
    } catch (err) {
      console.error('[DoctorDashboard] Failed to load patients:', err.message);
      _patients = [];
    }
    _renderTable(_patients);
    _updateStats();

    // Set a default patient so App.patientId is never empty
    if (_patients.length > 0 && !App.patientId) {
      App.setPatient(_patients[0].patient_uid);
    }
  }

  function _renderTable(patients) {
    Helpers.setText('patientCount', `${patients.length} patient${patients.length !== 1 ? 's' : ''}`);
    Helpers.setText('docStatPatients',  patients.length);
    Helpers.setText('docStatPatients2', patients.length);

    const tbody = document.getElementById('patientTableBody');
    if (!tbody) return;

    if (!patients.length) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">👤</div><div class="empty-text">No patients found</div></div></td></tr>`;
      return;
    }

    const colors = ['#00d4ff', '#7b5cff', '#00e5a0', '#ffb547', '#ff6b9d'];
    tbody.innerHTML = patients.map(p => {
      const sev  = p.latest_severity;
      const sc   = sev == null ? '' : sev >= 70 ? 'sev-high' : sev >= 40 ? 'sev-moderate' : 'sev-low';
      const st   = sev == null ? '—' : sev >= 70 ? '🔴 Critical' : sev >= 40 ? '🟡 Monitoring' : '🟢 Stable';
      const ac   = colors[Math.abs((p.id || 0) % 5)];
      const nm   = (p.name || p.patient_uid || '');
      const ini  = ((nm.split(' ')[0] || '')[0] + (nm.split(' ')[1] || '')[0]).toUpperCase();
      const date = p.latest_prediction?.created_at
        ? new Date(p.latest_prediction.created_at).toLocaleDateString() : '—';

      return `
        <tr onclick="DoctorDashboard.openPatient('${p.patient_uid}')">
          <td>
            <div class="pt-name-cell">
              <div class="pt-mini-avatar" style="background:${ac}">${ini || '?'}</div>
              <div>
                <div style="font-weight:500">${nm}</div>
                <div class="pt-uid">${p.patient_uid}</div>
              </div>
            </div>
          </td>
          <td>${p.age || '—'}</td>
          <td>${p.gender || '—'}</td>
          <td style="font-size:12px;color:var(--text-2)">Parkinson's Disease</td>
          <td>${sev != null
            ? `<span class="severity-pill ${sc}">${sev.toFixed(0)}</span>`
            : `<span style="color:var(--text-3);font-size:12px">No data</span>`}</td>
          <td style="font-size:12px">${st}</td>
          <td style="font-size:11px;font-family:var(--font-mono);color:var(--text-3)">${date}</td>
          <td>
            <button class="btn btn-ghost" style="font-size:11px;padding:5px 10px"
              onclick="event.stopPropagation();DoctorDashboard.openPatient('${p.patient_uid}')">
              View →
            </button>
          </td>
        </tr>`;
    }).join('');
  }

  function _updateStats() {
    const withSev = _patients.filter(p => p.latest_severity != null);
    const avg     = withSev.length
      ? Math.round(withSev.reduce((s, p) => s + p.latest_severity, 0) / withSev.length) : 0;
    const stable  = _patients.filter(p => (p.latest_severity || 0) < 40).length;
    const crit    = _patients.filter(p => (p.latest_severity || 0) >= 70).length;

    Helpers.setText('docAvgSeverity',  avg || '—');
    Helpers.setText('docStableCount',  stable);
    Helpers.setText('docCriticalCount', crit);
    Helpers.setText('docStatActive',   withSev.length);
    Helpers.setText('docStatCritical', crit);
  }

  function filterSeverity(level, btn) {
    document.querySelectorAll('.table-search-bar .btn')
      .forEach(b => b.classList.remove('btn-primary'));
    if (btn) btn.classList.add('btn-primary');

    const filtered = level === 'all'
      ? _patients
      : _patients.filter(p => {
          const s = p.latest_severity || 0;
          if (level === 'critical') return s >= 70;
          if (level === 'moderate') return s >= 40 && s < 70;
          if (level === 'stable')   return s < 40;
          return true;
        });
    _renderTable(filtered);
  }

  function openPatient(uid) {
    App.setPatient(uid);
    // Navigate to dashboard page which will call PageDashboard.load()
    // This shows the individual patient's data, not the doctor overview
    Router.navigate('dashboard');
  }

  function _ini(user) {
    if (!user) return '??';
    return ((user.first_name || '')[0] + (user.last_name || '')[0]).toUpperCase() || '??';
  }

  return { init, openPatient, filterSeverity };
})();