/* ============================================================
   static/js/auth/patient_dashboard.js  — FIXED
   Changes:
   - _loadData is now PUBLIC (exported) so realtime.js can call it
   - Status badge updates dynamically from API response
   - Reports section renders content from Report records
   - PDF download button added per report
   - Prediction count fetched from dashboard endpoint
   ============================================================ */

   const PatientDashboard = (() => {

    function init() {
      const user = Auth.getUser();
      const uid  = Auth.getPatientUid();
      if (uid) App.setPatient(uid);
      Sidebar.render();
      Topbar.render();
      _patchTopbar(user);
      Router.navigate('dashboard');
      _overrideView(user, uid || App.patientId);
    }
  
    function _patchTopbar(user) {
      const right = document.querySelector('.topbar-right');
      if (!right) return;
      const badge = document.createElement('span');
      badge.className   = 'role-badge patient';
      badge.textContent = '🧑 Patient';
      right.prepend(badge);
      const profileBtn = document.createElement('button');
      profileBtn.className = 'topbar-btn';
      profileBtn.setAttribute('data-tooltip', 'My Profile');
      profileBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
      profileBtn.addEventListener('click', () => _showProfile(user));
      right.insertBefore(profileBtn, right.lastElementChild);
      const logoutBtn = document.createElement('button');
      logoutBtn.className = 'topbar-btn';
      logoutBtn.setAttribute('data-tooltip', 'Sign out');
      logoutBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`;
      logoutBtn.addEventListener('click', () => Auth.logout());
      right.appendChild(logoutBtn);
      const sel = document.querySelector('.patient-select-wrap');
      if (sel) sel.style.display = 'none';
      Helpers.setText('topbarPatient', Auth.getPatientUid() || 'My Dashboard');
    }

    function _localDateStr(isoString) {
      if (!isoString) return '—';
      try {
        const d = new Date(isoString);
        return d.toLocaleString(undefined, {
          day: '2-digit', month: 'short', year: 'numeric',
          hour: '2-digit', minute: '2-digit', hour12: true,
        });
      } catch { return isoString; }
    }
  
    function _overrideView(user, uid) {
      const root = document.getElementById('page-dashboard');
      if (!root) return;
      root.dataset.inited = '1';
      const firstName = user?.first_name || 'Patient';
  
      root.innerHTML = `
        <div class="patient-welcome">
          <div class="welcome-avatar">${_ini(user)}</div>
          <div class="welcome-text">
            <div class="greeting">Welcome back, ${firstName} 👋</div>
            <div class="sub">Here's your personal health monitoring summary.</div>
            <div style="font-size:11px;font-family:var(--font-mono);color:var(--cyan);margin-top:6px">Patient ID: ${uid || '—'}</div>
          </div>
          <div class="welcome-actions">
            <button class="btn btn-primary" onclick="Router.navigate('realtime')">⚡ New Prediction</button>
            <button class="btn btn-ghost" onclick="PatientDashboard.showReports()">📋 My Reports</button>
          </div>
        </div>
  
        <div style="background:var(--cyan-dim);border:1px solid rgba(0,212,255,0.2);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:20px;font-size:12px;color:var(--cyan);display:flex;align-items:center;gap:8px">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          You are viewing only your own health data. Your information is private and secure.
        </div>
  
        <div id="patientStatsError"></div>
        <div id="patientStatsLoading">
          <div class="grid-4 section-gap">
            ${[1,2,3,4].map(() => `<div class="skeleton skeleton-card" style="height:100px"></div>`).join('')}
          </div>
        </div>
  
        <div id="patientStatsData" style="display:none">
          <div class="grid-4 section-gap">
            <div class="stat-card card-glow-cyan">
              <div class="stat-label">My Severity</div>
              <div class="stat-value text-cyan" id="mySeverity">—</div>
              <div class="stat-sub"><span id="myStage">—</span></div>
            </div>
            <div class="stat-card card-glow-violet">
              <div class="stat-label">UPDRS Score</div>
              <div class="stat-value text-violet" id="myUpdrs">—</div>
            </div>
            <div class="stat-card card-glow-green">
              <div class="stat-label">AI Confidence</div>
              <div class="stat-value text-green" id="myConfidence">—</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">My Predictions</div>
              <div class="stat-value text-amber" id="myPredCount">—</div>
            </div>
          </div>
  
          <div class="patient-card section-gap">
            <div class="patient-avatar">${_ini(user)}</div>
            <div class="patient-info">
              <div class="patient-name">${user?.first_name || ''} ${user?.last_name || ''}</div>
              <div class="patient-id">${uid || '—'}</div>
              <div class="patient-meta">
                <span class="meta-tag" id="myAge">Age: —</span>
                <span class="meta-tag" id="myGender">—</span>
                <span class="meta-tag" id="myDiagnosis">—</span>
                <span class="meta-tag" id="myOnset">Onset: —</span>
              </div>
            </div>
            <div class="patient-status">
              <span class="status-badge" id="myStatus">Loading…</span>
              <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-3)" id="myLastUpdated">—</span>
            </div>
          </div>
  
          <div class="card card-glow-cyan section-gap">
            <div class="card-header"><span class="card-title">My Progression Trend</span></div>
            <div class="chart-wrap" style="height:200px"><canvas id="myProgressionChart"></canvas></div>
          </div>
  
          <div class="card section-gap">
            <div class="card-header">
              <span class="card-title">My Reports</span>
              <div class="card-icon" style="background:var(--violet-dim)">📋</div>
            </div>
            <div id="myReportsList"><div class="loading-overlay"><div class="spinner"></div> Loading…</div></div>
          </div>
  
          <div class="card">
            <div class="card-header"><span class="card-title">My Alerts</span></div>
            <div class="alert-list" id="myAlertList"><div class="loading-overlay"><div class="spinner"></div></div></div>
          </div>
        </div>
  
        <!-- Modals -->
        <div class="modal-backdrop" id="profileModal">
          <div class="modal">
            <div class="modal-header">
              <span class="modal-title">My Profile</span>
              <button class="modal-close" onclick="document.getElementById('profileModal').classList.remove('open')">✕</button>
            </div>
            <div id="profileModalContent"></div>
          </div>
        </div>
        <div class="modal-backdrop" id="reportsModal">
          <div class="modal" style="max-width:660px">
            <div class="modal-header">
              <span class="modal-title">My Reports</span>
              <button class="modal-close" onclick="document.getElementById('reportsModal').classList.remove('open')">✕</button>
            </div>
            <div id="reportsModalContent" style="max-height:65vh;overflow-y:auto"></div>
          </div>
        </div>`;
  
      _loadData(uid);
    }
  
    // ── PUBLIC: called by realtime.js after a prediction ────────
    async function _loadData(uid) {
      if (!uid) return;
  
      try {
        const res = await API.getDashboard(uid);
        const d   = res.data;
  
        Helpers.hide('patientStatsLoading');
        Helpers.show('patientStatsData');
  
        // Stats
        Helpers.setText('mySeverity',   d.severity != null ? `${d.severity}` : '—');
        Helpers.setText('myStage',      d.stage || '—');
        Helpers.setText('myUpdrs',      d.updrs != null ? `${d.updrs}` : '—');
        Helpers.setText('myConfidence', d.fusion_confidence != null ? `${Helpers.pct(d.fusion_confidence)}%` : '—');
        Helpers.setText('myAge',        `Age: ${d.age || '—'}`);
        Helpers.setText('myGender',     d.gender || '—');
        Helpers.setText('myDiagnosis',  d.diagnosis || '—');
        Helpers.setText('myOnset',      `Onset: ${d.onset || '—'}`);
        Helpers.setText('myLastUpdated', `Updated: ${Helpers.timeNow()}`);
        // Prediction count (from dashboard endpoint)
        if (d.total_predictions != null) {
          Helpers.setText('myPredCount', d.total_predictions);
        }
  
        // ── Status badge — dynamic from severity ─────────────────
        const sb = document.getElementById('myStatus');
        if (sb) {
          const statusMap = {
            stable:   { label: '🟢 Stable',      cls: 'status-stable'   },
            warning:  { label: '🟡 Moderate Risk', cls: 'status-warning'  },
            critical: { label: '🔴 High Risk',    cls: 'status-critical' },
          };
          const s = statusMap[d.status] || statusMap.stable;
          sb.textContent = s.label;
          sb.className   = `status-badge ${s.cls}`;
        }
  
        _renderAlerts(d.alerts || []);
  
      } catch (err) {
        console.error('[PatientDashboard] getDashboard failed:', err.message);
        Helpers.showError('patientStatsError', `Failed to load dashboard: ${err.message}`);
        Helpers.hide('patientStatsLoading');
        Helpers.show('patientStatsData');
      }
  
      // Prediction count fallback via separate endpoint
      try {
        const r = await API.getPatientPredictions(uid);
        if (document.getElementById('myPredCount')?.textContent === '—') {
          Helpers.setText('myPredCount', r.data?.total ?? '—');
        }
      } catch { /* silent */ }
  
      // ── Progression chart ─────────────────────────────────────
      try {
        const r = await API.getHistory(uid);
        const h = r.data;
        if (h?.labels?.length > 0 && h?.severity?.some(v => v != null)) {
          const ctx = document.getElementById('myProgressionChart')?.getContext('2d');
          if (ctx) {
            Charts.create('myProgression', ctx, {
              type: 'line',
              data: {
                labels: h.labels,
                datasets: [{
                  label: 'Severity',
                  data:  h.severity,
                  borderColor:     '#00d4ff',
                  backgroundColor: Charts.gradientFill(ctx, '00d4ff', 200),
                  fill: true, tension: 0.4, borderWidth: 2, pointRadius: 3,
                }],
              },
              options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: Charts.TOOLTIP },
                scales: {
                  x: { ...Charts.SCALE.x, ticks: { maxTicksLimit: 8 } },
                  y: { ...Charts.SCALE.y, min: 0, max: 100 },
                },
              },
            });
          }
        } else {
          // No history yet — show placeholder
          const wrap = document.getElementById('myProgressionChart')?.parentElement;
          if (wrap) wrap.innerHTML = `<div class="empty-state" style="padding:30px"><div class="empty-icon">📈</div><div class="empty-text">No history yet — run more predictions</div></div>`;
        }
      } catch (err) {
        console.warn('[PatientDashboard] History chart failed:', err.message);
      }
  
      // ── Reports ───────────────────────────────────────────────
      _loadReports(uid, 'myReportsList', 5);
    }
  
    async function _loadReports(uid, containerId, limit = null) {
      try {
        const r = await API.getPatientReports(uid);
        let reports = (r.data?.reports || [])
          .slice()
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        const shown  = limit ? reports.slice(0, limit) : reports;
        const total  = reports.length;
        const hidden = limit ? Math.max(0, total - limit) : 0;
        if (!shown.length) {
          Helpers.setHTML(containerId,
            `<div class="empty-state"><div class="empty-icon">📋</div>
             <div class="empty-text">No reports yet</div>
             <div class="empty-sub">Reports are generated automatically after each prediction</div></div>`);
          return;
        }
        const moreHtml = hidden > 0
          ? `<div style="text-align:center;padding:12px 0;border-top:1px solid var(--glass-border);margin-top:8px">
               <button class="btn btn-ghost" style="font-size:12px"
                 onclick="PatientDashboard.showReports()">View all ${total} reports →</button></div>`
          : '';
        Helpers.setHTML(containerId, shown.map(rp => _reportCard(rp)).join('') + moreHtml);
      } catch {
        Helpers.setHTML(containerId,
          `<div class="empty-state"><div class="empty-text">Could not load reports</div></div>`);
      }
    }
  
    function _reportCard(rp) {
      const c = rp.content || {};
      const date = _localDateStr(rp.created_at);
      const sev  = c.severity   != null ? `${c.severity}`     : '—';
      const conf = c.confidence != null ? `${c.confidence}%` : '—';
      return `
        <div class="report-card section-gap"
             style="border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:14px;margin-bottom:10px">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
            <div style="font-weight:600;font-size:13px">${rp.title || 'Report'}</div>
            <button class="btn btn-ghost" style="font-size:11px;padding:4px 10px"
                    onclick="PatientDashboard.downloadReport(${rp.id})">⬇ PDF</button>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;font-size:11px;font-family:var(--font-mono);color:var(--text-3)">
            <span>📅 ${date}</span>
            <span>🔬 ${c.model_used || '—'}</span>
            <span>🎯 ${c.result || '—'}</span>
            <span>📊 Severity: ${sev}</span>
            <span>✅ Confidence: ${conf}</span>
          </div>
          ${c.notes ? `<div style="font-size:12px;color:var(--text-2);margin-top:8px;line-height:1.6">${c.notes}</div>` : ''}
        </div>`;
    }
  
    function downloadReport(reportId) {
      const uid = Auth.getPatientUid() || App.patientId;
      API.getPatientReports(uid).then(r => {
        const rp = (r.data?.reports || []).find(x => x.id === reportId);
        if (!rp) return;
        const c = rp.content || {};
        const user = Auth.getUser();
        const win = window.open('', '_blank');
        win.document.write(`<!DOCTYPE html><html><head><title>${rp.title}</title>
          <style>body{font-family:Arial,sans-serif;padding:40px;max-width:700px;margin:auto}
          h1{color:#0a1628;border-bottom:2px solid #00d4ff;padding-bottom:10px}
          table{width:100%;border-collapse:collapse;margin-top:20px}
          td,th{padding:10px;border:1px solid #ddd;text-align:left}th{background:#f0f8ff}
          .footer{margin-top:40px;font-size:11px;color:#aaa;border-top:1px solid #eee;padding-top:12px}
          </style></head><body>
          <h1>NeuroTrace — ${rp.title}</h1>
          <p><strong>Patient:</strong> ${user?.first_name||''} ${user?.last_name||''} (${Auth.getPatientUid()||'—'})
          &nbsp;|&nbsp;<strong>Date:</strong> ${_localDateStr(rp.created_at)}</p>
          <table>
            <tr><th>Field</th><th>Value</th></tr>
            <tr><td>Model</td><td>${c.model_used||'—'}</td></tr>
            <tr><td>Result</td><td>${c.result||'—'}</td></tr>
            <tr><td>Severity</td><td>${c.severity!=null?c.severity:'—'}</td></tr>
            <tr><td>Confidence</td><td>${c.confidence!=null?c.confidence+'%':'—'}</td></tr>
            <tr><td>Stage</td><td>${c.stage||'—'}</td></tr>
            <tr><td>Has Parkinson's</td><td>${c.has_parkinson!=null?(c.has_parkinson?'Yes':'No'):'—'}</td></tr>
          </table>
          <p style="margin-top:20px">${c.notes||''}</p>
          <div class="footer">Generated by NeuroTrace · ${_localDateStr(new Date().toISOString())}</div>
          <script>window.print();<\/script></body></html>`);
        win.document.close();
      }).catch(() => alert('Could not load report'));
    }
  
    function _renderAlerts(alerts) {
      Helpers.setHTML('myAlertList', alerts.length
        ? alerts.map(a => `
            <div class="alert-item alert-${a.type || 'info'}">
              <div class="alert-header">
                <span class="alert-type">${a.type || 'info'}</span>
                <span class="alert-time">${a.time || ''}</span>
              </div>
              <div class="alert-msg">${a.msg || ''}</div>
            </div>`).join('')
        : `<div class="empty-state"><div class="empty-icon">✅</div><div class="empty-text">No active alerts</div></div>`
      );
    }
  
    function showReports() {
      const modal = document.getElementById('reportsModal');
      if (!modal) return;
      modal.classList.add('open');
      const uid = Auth.getPatientUid() || App.patientId;
      Helpers.setHTML('reportsModalContent', '<div class="loading-overlay"><div class="spinner"></div> Loading…</div>');
      _loadReports(uid, 'reportsModalContent');
    }
  
    function _showProfile(user) {
      const modal = document.getElementById('profileModal');
      if (!modal) return;
      modal.classList.add('open');
      const uid = Auth.getPatientUid();
      Helpers.setHTML('profileModalContent', `
        <div style="display:flex;flex-direction:column;gap:16px">
          <div style="display:flex;align-items:center;gap:14px">
            <div style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,var(--green),var(--cyan));display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-size:20px;font-weight:800;color:white">${_ini(user)}</div>
            <div>
              <div style="font-family:var(--font-display);font-size:18px;font-weight:700">${user?.first_name || ''} ${user?.last_name || ''}</div>
              <div style="font-size:11px;font-family:var(--font-mono);color:var(--cyan)">${uid || '—'}</div>
            </div>
          </div>
          ${_row('Email',      user?.email || '—')}
          ${_row('Role',       'Patient')}
          ${_row('Patient ID', uid || '—')}
          <button class="auth-submit" onclick="Auth.logout()" style="margin-top:8px">Sign Out</button>
        </div>`);
    }
  
    function _row(label, value) {
      return `<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--glass);border:1px solid var(--glass-border);border-radius:var(--radius-sm)"><span style="font-size:11px;font-family:var(--font-mono);color:var(--text-3);text-transform:uppercase;letter-spacing:1px">${label}</span><span style="font-size:13px;font-weight:500">${value}</span></div>`;
    }
  
    function _ini(user) {
      if (!user) return '??';
      return ((user.first_name || '')[0] + (user.last_name || '')[0]).toUpperCase() || '??';
    }
  
    // Expose _loadData publicly so realtime.js can trigger a refresh
    return { init, showReports, downloadReport, _loadData };
  })();