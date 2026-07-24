/* ============================================================
   static/js/auth/auth_ui.js
   ──────────────────────────────────────────────────────────
   ============================================================ */

const AuthUI = (() => {

  /* ── Show / hide auth shell ──────────────────────────── */
  function showLogin()  { _renderShell('login');  }
  function showSignup() { _renderShell('signup'); }

  function hideAuth() {
    document.getElementById('auth-shell')?.remove();
    const sidebar = document.getElementById('sidebar-root');
    const main    = document.getElementById('main-shell');
    if (sidebar) sidebar.style.display = '';
    if (main)    main.style.display    = '';
  }

  /* ── Shell injector ─────────────────────────────────── */
  function _renderShell(view) {
    // Hide the main app while auth is showing
    const sidebar = document.getElementById('sidebar-root');
    const main    = document.getElementById('main-shell');
    if (sidebar) sidebar.style.display = 'none';
    if (main)    main.style.display    = 'none';

    document.getElementById('auth-shell')?.remove();

    const shell = document.createElement('div');
    shell.id        = 'auth-shell';
    shell.className = 'auth-shell';
    shell.innerHTML = view === 'login' ? _loginHTML() : _signupHTML();
    document.body.appendChild(shell);

    if (view === 'login')  _bindLogin();
    else                   _bindSignup();
  }

  /* ── Login HTML ─────────────────────────────────────── */
  function _loginHTML() {
    return `
      <div class="auth-card">
        <div class="auth-logo">
          <div class="auth-logo-icon">🧠</div>
          <div>
            <div class="auth-logo-name">NeuroTrace</div>
            <div class="auth-logo-tagline">Parkinson's Intelligence Platform</div>
          </div>
        </div>

        <div class="auth-title">Welcome back</div>
        <div class="auth-subtitle">Sign in to access your dashboard</div>

        <div class="auth-alert" id="loginAlert"></div>

        <form class="auth-form" id="loginForm" autocomplete="on">
          <div class="form-group">
            <label class="form-label">Email address</label>
            <div class="form-input-wrap">
              <svg class="form-input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
              <input type="email" class="form-input" id="loginEmail"
                     placeholder="doctor@neurotrace.ai" autocomplete="email" required />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <div class="form-input-wrap">
              <svg class="form-input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <input type="password" class="form-input" id="loginPassword"
                     placeholder="••••••••" autocomplete="current-password" required />
              <button type="button" class="form-input-toggle" id="loginPassToggle" aria-label="Show password">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>

          <button type="submit" class="auth-submit" id="loginBtn">Sign In</button>
        </form>

        <div class="auth-divider">demo accounts</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <button class="btn btn-ghost" onclick="AuthUI.fillDemo('doctor')" style="font-size:12px;justify-content:center">
            👨‍⚕️ Doctor Demo
          </button>
          <button class="btn btn-ghost" onclick="AuthUI.fillDemo('patient')" style="font-size:12px;justify-content:center">
            🧑 Patient Demo
          </button>
        </div>

        <div class="auth-footer">
          Don't have an account?
          <button class="auth-link" onclick="AuthUI.showSignup()">Create account</button>
        </div>
      </div>`;
  }

  /* ── Signup HTML ────────────────────────────────────── */
  function _signupHTML() {
    return `
      <div class="auth-card">
        <div class="auth-logo">
          <div class="auth-logo-icon">🧠</div>
          <div>
            <div class="auth-logo-name">NeuroTrace</div>
            <div class="auth-logo-tagline">Parkinson's Intelligence Platform</div>
          </div>
        </div>

        <div class="auth-steps">
          <div class="auth-step active" id="step1"></div>
          <div class="auth-step"        id="step2"></div>
        </div>

        <div id="signupStep1">
          <div class="auth-title">Create account</div>
          <div class="auth-subtitle">Choose your role to get started</div>
          <div class="auth-alert" id="signupAlert"></div>

          <form class="auth-form" id="signupForm1">
            <div class="form-group">
              <label class="form-label">I am a</label>
              <div class="role-selector">
                <label class="role-option">
                  <input type="radio" name="role" value="doctor" />
                  <div class="role-card"><div class="role-icon">👨‍⚕️</div><div class="role-name">Doctor</div><div class="role-desc">View all patients</div></div>
                </label>
                <label class="role-option">
                  <input type="radio" name="role" value="patient" />
                  <div class="role-card"><div class="role-icon">🧑</div><div class="role-name">Patient</div><div class="role-desc">View my own data</div></div>
                </label>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">First name</label>
                <input type="text" class="form-input" id="signupFirst" placeholder="James" required />
              </div>
              <div class="form-group">
                <label class="form-label">Last name</label>
                <input type="text" class="form-input" id="signupLast" placeholder="Harrington" required />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Email address</label>
              <div class="form-input-wrap">
                <svg class="form-input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                <input type="email" class="form-input" id="signupEmail" placeholder="you@hospital.com" required />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Password (min 8 chars)</label>
              <div class="form-input-wrap">
                <svg class="form-input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <input type="password" class="form-input" id="signupPassword" placeholder="Min 8 characters" required minlength="8" />
              </div>
            </div>
            <button type="submit" class="auth-submit" id="signupNext">Continue →</button>
          </form>
        </div>

        <div id="signupStep2" style="display:none">
          <div class="auth-title" id="step2Title">Almost there</div>
          <div class="auth-subtitle" id="step2Subtitle">A few more details</div>
          <div class="auth-alert" id="signupAlert2"></div>
          <form class="auth-form" id="signupForm2">
            <div id="doctorFields" style="display:none">
              <div class="form-group">
                <label class="form-label">Specialisation</label>
                <input type="text" class="form-input" id="doctorSpec" placeholder="Neurology" />
              </div>
              <div class="form-group">
                <label class="form-label">License Number</label>
                <input type="text" class="form-input" id="doctorLicense" placeholder="NRL-2024-001" />
              </div>
            </div>
            <div id="patientFields" style="display:none">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Age</label>
                  <input type="number" class="form-input" id="patientAge" placeholder="65" min="1" max="120" />
                </div>
                <div class="form-group">
                  <label class="form-label">Gender</label>
                  <select class="form-input" id="patientGender">
                    <option value="">Select</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">Diagnosis onset year</label>
                <input type="number" class="form-input" id="patientOnset" placeholder="2020" min="1900" max="2099" />
              </div>
            </div>
            <div style="display:flex;gap:10px;margin-top:4px">
              <button type="button" class="btn btn-ghost" onclick="AuthUI._backToStep1()">← Back</button>
              <button type="submit" class="auth-submit" id="signupSubmit" style="flex:1">Create Account</button>
            </div>
          </form>
        </div>

        <div class="auth-footer">
          Already have an account?
          <button class="auth-link" onclick="AuthUI.showLogin()">Sign in</button>
        </div>
      </div>`;
  }

  /* ── Login binding ─────────────────────────────────── */
  function _bindLogin() {
    document.getElementById('loginPassToggle')?.addEventListener('click', () => {
      const inp = document.getElementById('loginPassword');
      inp.type  = inp.type === 'password' ? 'text' : 'password';
    });

    document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email    = document.getElementById('loginEmail').value.trim();
      const password = document.getElementById('loginPassword').value;
      const btn      = document.getElementById('loginBtn');

      btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div> Signing in…';
      btn.disabled  = true;

      try {
        const data = await Auth.login(email, password);
        _alert('loginAlert', '', false);
        _onSuccess(data);
      } catch (err) {
        _alert('loginAlert', err.message, true);
        btn.innerHTML = 'Sign In';
        btn.disabled  = false;
      }
    });
  }

  /* ── Signup binding ─────────────────────────────────── */
  function _bindSignup() {
    document.getElementById('signupForm1')?.addEventListener('submit', (e) => {
      e.preventDefault();
      const role = document.querySelector('input[name="role"]:checked')?.value;
      if (!role) { _alert('signupAlert', 'Please select Doctor or Patient', true); return; }
      _goStep2(role);
    });

    document.getElementById('signupForm2')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('signupSubmit');
      btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div> Creating…';
      btn.disabled  = true;
      try {
        const data = await Auth.signup(_buildPayload());
        _onSuccess(data);
      } catch (err) {
        _alert('signupAlert2', err.message, true);
        btn.innerHTML = 'Create Account';
        btn.disabled  = false;
      }
    });
  }

  function _goStep2(role) {
    document.getElementById('signupStep1').style.display = 'none';
    document.getElementById('signupStep2').style.display = '';
    document.getElementById('step1').classList.replace('active','done');
    document.getElementById('step2').classList.add('active');
    if (role === 'doctor') {
      document.getElementById('step2Title').textContent    = 'Doctor details';
      document.getElementById('step2Subtitle').textContent = 'Add your professional info (optional)';
      document.getElementById('doctorFields').style.display  = '';
      document.getElementById('patientFields').style.display = 'none';
    } else {
      document.getElementById('step2Title').textContent    = 'Patient profile';
      document.getElementById('step2Subtitle').textContent = 'Help us personalise your dashboard';
      document.getElementById('doctorFields').style.display  = 'none';
      document.getElementById('patientFields').style.display = '';
    }
  }

  function _backToStep1() {
    document.getElementById('signupStep1').style.display = '';
    document.getElementById('signupStep2').style.display = 'none';
    document.getElementById('step1').classList.replace('done','active');
    document.getElementById('step2').classList.remove('active');
  }

  function _buildPayload() {
    const role = document.querySelector('input[name="role"]:checked')?.value;
    const p = {
      first_name: document.getElementById('signupFirst').value.trim(),
      last_name:  document.getElementById('signupLast').value.trim(),
      email:      document.getElementById('signupEmail').value.trim(),
      password:   document.getElementById('signupPassword').value,
      role,
    };
    if (role === 'doctor') {
      p.specialisation  = document.getElementById('doctorSpec').value.trim() || 'Neurology';
      p.license_number  = document.getElementById('doctorLicense').value.trim();
    } else {
      const age   = parseInt(document.getElementById('patientAge').value);
      const onset = parseInt(document.getElementById('patientOnset').value);
      if (!isNaN(age))   p.age        = age;
      if (!isNaN(onset)) p.onset_year = onset;
      p.gender = document.getElementById('patientGender').value || undefined;
    }
    return p;
  }

  function _onSuccess(data) {
    hideAuth();
    const role = data.user?.role || Auth.getRole();
    if (role === 'doctor') DoctorDashboard.init();
    else                   PatientDashboard.init();
  }

  /* ── Demo credentials (match seeded users exactly) ── */
  function fillDemo(role) {
    const creds = {
      doctor:  { email: 'doctor@neurotrace.ai',  password: 'Doctor123!'  },
      patient: { email: 'james.h@neurotrace.ai', password: 'Patient123!' },
    };
    const { email, password } = creds[role] || creds.patient;
    const eEl = document.getElementById('loginEmail');
    const pEl = document.getElementById('loginPassword');
    if (eEl) eEl.value = email;
    if (pEl) pEl.value = password;
  }

  function _alert(id, msg, isError) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!msg) { el.className = 'auth-alert'; return; }
    el.textContent = msg;
    el.className   = `auth-alert visible ${isError ? 'error' : 'success'}`;
  }

  return { showLogin, showSignup, hideAuth, fillDemo, _backToStep1 };
})();