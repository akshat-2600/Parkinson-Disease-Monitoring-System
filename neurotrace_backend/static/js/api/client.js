/* ============================================================
   static/js/api/client.js  
  */


const API = (() => {

  // Use relative paths — works for any host/port since Flask serves both
  // the HTML and the API from the same origin.
  const API_ROOT = '/api';

  /* ── Core request helper ─────────────────────────────── */
  async function _request(method, path, body = null) {
    const url    = API_ROOT + path;
    const token  = (typeof Auth !== 'undefined') ? Auth.getToken() : null;
    const isForm = body instanceof FormData;
    if (!token) {
      console.debug('[API] No access token found in localStorage for request', method, path);
    }

    // Build headers
    const headers = {};
    if (token) {
      // Only add Authorization when token is a real string (not null/undefined)
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (!isForm && body !== null) {
      headers['Content-Type'] = 'application/json';
    }
    // FormData: let browser set Content-Type with boundary automatically

    const options = { method, headers };
    if (body !== null) {
      options.body = isForm ? body : JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(url, options);
    } catch (networkErr) {
      throw new Error(`Network error calling ${method} ${url}: ${networkErr.message}`);
    }

    // Handle 401 — attempt token refresh once then retry
    if (res.status === 401 && typeof Auth !== 'undefined') {
      console.log(`[API] 401 on ${method} ${path} — attempting token refresh`);
      const refreshed = await Auth._tryRefresh();
      if (refreshed) {
        const newToken = Auth.getToken();
        if (newToken) headers['Authorization'] = `Bearer ${newToken}`;
        res = await fetch(url, { method, headers, body: options.body });
      } else {
        console.warn('[API] Refresh failed — clearing session and redirecting to login');
        Auth.clearSession();
        if (typeof AuthUI !== 'undefined') AuthUI.showLogin();
        throw new Error('Your session has expired. Please log in again.');
      }
    }

    // Parse JSON response
    let json;
    try {
      json = await res.json();
    } catch {
      throw new Error(`Non-JSON response from ${method} ${path} (HTTP ${res.status})`);
    }

    if (!res.ok) {
      const msg = json?.message || json?.error || `HTTP ${res.status}: ${res.statusText}`;
      throw new Error(msg);
    }

    return json;
  }

  const _get  = (path)       => _request('GET',    path);
  const _post = (path, body) => _request('POST',   path, body);
  const _put  = (path, body) => _request('PUT',    path, body);
  const _del  = (path)       => _request('DELETE', path);

  /* ────────────────────────────────────────────────────────
     Auth endpoints (login/signup do NOT need a token)
     These bypass _request() to avoid the token check.
     ──────────────────────────────────────────────────────── */
  // Note: Auth.login() and Auth.signup() call fetch() directly now.
  // These are kept here as thin wrappers only if called externally.
  const refreshToken = (rt) =>
    fetch(API_ROOT + '/auth/refresh', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${rt}` },
    }).then(r => r.json());

  const logout = () => _del('/auth/logout');
  const getMe  = () => _get('/auth/me');

  /* ── Per-modality individual prediction ──────────────── */
  const predictVoice    = (fd) => _post('/voice/predict',    fd);
  const predictMri      = (fd) => _post('/mri/predict',      fd);
  const predictSpiral   = (fd) => _post('/spiral/predict',   fd);
  const predictClinical = (fd) => _post('/clinical/predict', fd);
  const predictMotor    = (fd) => _post('/motor/predict',    fd);

  /* ── Fusion endpoints ─────────────────────────────────── */
  const realtimePredict    = (fd)  => _post('/fusion/realtime_predict', fd);
  const getDashboard       = (pid) => _get(`/fusion/dashboard/${pid}`);
  const getExplanation     = (pid) => _get(`/fusion/explanation/${pid}`);
  const getRecommendations = (pid) => _get(`/fusion/recommendations/${pid}`);
  const getHistory         = (pid) => _get(`/fusion/history/${pid}`);

  /* ── Patient management ───────────────────────────────── */
  // FIXED: listPatients(page, perPage) — NO token parameter
  const listPatients          = (page = 1, pp = 200) => _get(`/patients/?page=${page}&per_page=${pp}`);
  const getPatient            = (pid) => _get(`/patients/${pid}`);
  const getPatientPredictions = (pid) => _get(`/patients/${pid}/predictions`);
  const getPatientReports     = (pid) => _get(`/patients/${pid}/reports`);
  const updatePatient         = (pid, body) => _put(`/patients/${pid}`, body);

  return {
    API_ROOT,
    refreshToken, logout, getMe,
    predictVoice, predictMri, predictSpiral, predictClinical, predictMotor,
    realtimePredict,
    getDashboard, getExplanation, getRecommendations, getHistory,
    listPatients, getPatient, getPatientPredictions, getPatientReports, updatePatient,
    _request,  // exposed for one-off calls
  };
})();