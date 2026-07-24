/* ============================================================
   static/js/auth/auth.js  */

const Auth = (() => {

  const KEYS = {
    TOKEN:       'nt_access_token',
    REFRESH:     'nt_refresh_token',
    USER:        'nt_user',
    PATIENT_UID: 'nt_patient_uid',
    DOCTOR_ID:   'nt_doctor_id',
  };

  /* ── Storage helpers ─────────────────────────────────── */
  function _store(key, value) {
    if (value != null && value !== 'undefined' && value !== 'null') {
      localStorage.setItem(key, String(value));
    }
  }

  function saveSession(data) {
    if (!data) return;
    // data is the inner payload: { access_token, refresh_token, user, patient_uid?, doctor_id? }
    _store(KEYS.TOKEN,       data.access_token);
    _store(KEYS.REFRESH,     data.refresh_token);
    if (data.user) localStorage.setItem(KEYS.USER, JSON.stringify(data.user));
    if (data.patient_uid) _store(KEYS.PATIENT_UID, data.patient_uid);
    if (data.doctor_id)   _store(KEYS.DOCTOR_ID,   data.doctor_id);
  }

  function clearSession() {
    Object.values(KEYS).forEach(k => localStorage.removeItem(k));
  }

  /* ── Getters — never return "null" / "undefined" strings ── */
  function getToken() {
    const t = localStorage.getItem(KEYS.TOKEN);
    return (t && t !== 'null' && t !== 'undefined') ? t : null;
  }

  function getRefresh() {
    const t = localStorage.getItem(KEYS.REFRESH);
    return (t && t !== 'null' && t !== 'undefined') ? t : null;
  }

  function getUser() {
    try { return JSON.parse(localStorage.getItem(KEYS.USER)) || null; }
    catch { return null; }
  }

  const getRole       = () => (getUser() || {}).role || null;
  const getPatientUid = () => {
    const v = localStorage.getItem(KEYS.PATIENT_UID);
    return (v && v !== 'null' && v !== 'undefined') ? v : null;
  };
  const isLoggedIn = () => !!(getToken() && getUser());

  /* ── Token refresh (called by client.js on 401) ──────── */
  async function _tryRefresh() {
    const rt = getRefresh();
    if (!rt) {
      console.warn('[Auth] No refresh token in storage — cannot refresh');
      return false;
    }
    try {
      // Direct fetch — do NOT go through API module (avoids circular 401 loop)
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${rt}` },
      });
      if (!res.ok) {
        console.warn('[Auth] Refresh returned', res.status);
        return false;
      }
      const json = await res.json();
      // Flask returns { status: "success", data: { access_token: "...", refresh_token: "..." } }
      const newToken = json?.data?.access_token || json?.access_token;
      const newRefresh = json?.data?.refresh_token || json?.refresh_token;
      if (!newToken) {
        console.warn('[Auth] Refresh response missing access token');
        return false;
      }

      localStorage.setItem(KEYS.TOKEN, newToken);
      if (newRefresh) {
        localStorage.setItem(KEYS.REFRESH, newRefresh);
      }

      console.log('[Auth] Token refreshed successfully');
      return true;
    } catch (err) {
      console.warn('[Auth] Refresh error:', err.message);
      return false;
    }
  }

  /* ── Login ────────────────────────────────────────────── */
  async function login(email, password) {
    // Direct fetch for login — token not needed
    const res = await fetch('/api/auth/login', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ email, password }),
    });

    let json;
    try { json = await res.json(); } catch { throw new Error('Server error — invalid response'); }

    if (!res.ok) {
      throw new Error(json?.message || json?.error || `Login failed (${res.status})`);
    }

    // Flask success response: { status: "success", data: { user, access_token, refresh_token, ... } }
    const data = json?.data || json;

    if (!data?.access_token) {
      console.error('[Auth] login response missing access_token:', json);
      throw new Error('Login succeeded but no token was returned. Check Flask logs.');
    }
    if (!data?.refresh_token) {
      console.error('[Auth] login response missing refresh_token:', json);
    }

    // Save session IMMEDIATELY — synchronously before anything else runs
    saveSession(data);

    // Verify it saved correctly
    const saved = getToken();
    if (!saved) {
      throw new Error('Token was returned but could not be saved to localStorage. Check browser privacy settings.');
    }

    console.log('[Auth] Login successful. Token saved. Role:', data.user?.role);
    return data;
  }

  /* ── Signup ───────────────────────────────────────────── */
  async function signup(payload) {
    const res = await fetch('/api/auth/signup', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    let json;
    try { json = await res.json(); } catch { throw new Error('Server error — invalid response'); }

    if (!res.ok) {
      throw new Error(json?.message || json?.error || `Signup failed (${res.status})`);
    }

    const data = json?.data || json;
    if (!data?.access_token) throw new Error('Signup succeeded but no token was returned.');

    saveSession(data);
    console.log('[Auth] Signup successful. Token saved. Role:', data.user?.role);
    return data;
  }

  /* ── Logout ───────────────────────────────────────────── */
  async function logout() {
    const tok = getToken();
    clearSession();
    try {
      if (tok) {
        await fetch('/api/auth/logout', {
          method:  'DELETE',
          headers: { 'Authorization': `Bearer ${tok}` },
        });
      }
    } catch { /* ignore network errors on logout */ }
    if (typeof AuthUI !== 'undefined') AuthUI.showLogin();
  }

  return {
    saveSession, clearSession,
    getToken, getRefresh, getUser, getRole, getPatientUid, isLoggedIn,
    login, signup, logout,
    _tryRefresh,  // exposed for client.js
  };
})();