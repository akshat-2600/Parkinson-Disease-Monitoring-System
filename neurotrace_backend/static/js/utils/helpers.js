/* ============================================================
   js/utils/helpers.js — General-purpose utilities
   ============================================================ */

const Helpers = (() => {

  /** Get initials from a full name */
  function initials(name = '') {
    return name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  }

  /** Format a JS Date to "HH:MM:SS" */
  function timeNow() {
    return new Date().toLocaleTimeString();
  }

  /** Safe integer percentage from 0–1 float */
  function pct(val) {
    return Math.round((val || 0) * 100);
  }

  /** Clamp a number between min and max */
  function clamp(val, min, max) {
    return Math.min(max, Math.max(min, val));
  }

  /** Show an error banner inside a container element */
  function showError(containerId, msg) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = `<div class="error-banner">⚠️ ${msg}. Showing fallback data.</div>`;
  }

  /** Clear the error banner inside a container element */
  function clearError(containerId) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = '';
  }

  /** Build a simple loading overlay string */
  function loadingHTML(text = 'Loading…') {
    return `<div class="loading-overlay"><div class="spinner"></div>${text}</div>`;
  }

  /** Safely set innerHTML of an element by id */
  function setHTML(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  /** Safely set textContent of an element by id */
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  /** Show / hide an element by id */
  function show(id) { const el = document.getElementById(id); if (el) el.style.display = ''; }
  function hide(id) { const el = document.getElementById(id); if (el) el.style.display = 'none'; }

  /** Palette for modality / feature bar colours */
  const PALETTE = ['#00d4ff', '#7b5cff', '#00e5a0', '#ffb547', '#ff6b9d', '#00d4ff', '#7b5cff', '#00e5a0'];

  return { initials, timeNow, pct, clamp, showError, clearError, loadingHTML, setHTML, setText, show, hide, PALETTE };
})();
