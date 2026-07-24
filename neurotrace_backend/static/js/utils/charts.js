/* ============================================================
   js/utils/charts.js — Chart.js defaults & factory helpers
   ============================================================ */

const Charts = (() => {

  /* Registry so every page can destroy old instances */
  const _registry = {};

  /* ── Apply global Chart.js defaults ── */
  function applyDefaults() {
    Chart.defaults.color        = '#8892b0';
    Chart.defaults.borderColor  = 'rgba(255,255,255,0.06)';
    Chart.defaults.font.family  = "'DM Mono', monospace";
    Chart.defaults.font.size    = 11;
  }

  /* ── Shared tooltip style ── */
  const TOOLTIP = {
    backgroundColor: '#131a30',
    borderColor: 'rgba(0,212,255,0.3)',
    borderWidth: 1,
    titleColor: '#f0f4ff',
    bodyColor:  '#8892b0',
    mode: 'index',
    intersect: false,
  };

  /* ── Shared scale style ── */
  const SCALE = {
    x: { grid: { color: 'rgba(255,255,255,0.04)' } },
    y: { grid: { color: 'rgba(255,255,255,0.04)' } },
  };

  /* ── Vertical gradient fill helper ── */
  function gradientFill(ctx, color, height = 220) {
    const g = ctx.createLinearGradient(0, 0, 0, height);
    const hex = color.replace('#', '');
    const r = parseInt(hex.slice(0,2),16);
    const c = parseInt(hex.slice(2,4),16);
    const b = parseInt(hex.slice(4,6),16);
    g.addColorStop(0, `rgba(${r},${c},${b},0.25)`);
    g.addColorStop(1, `rgba(${r},${c},${b},0)`);
    return g;
  }

  /* ── Destroy + create helper ── */
  function create(key, ctx, config) {
    if (_registry[key]) { _registry[key].destroy(); }
    _registry[key] = new Chart(ctx, config);
    return _registry[key];
  }

  function destroy(key) {
    if (_registry[key]) { _registry[key].destroy(); delete _registry[key]; }
  }

  /* ── Pre-built chart factories ── */

  function line(key, canvasId, labels, datasets, opts = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return;
    return create(key, ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: TOOLTIP },
        scales: {
          x: { ...SCALE.x, ticks: { maxTicksLimit: opts.maxX || 8 } },
          y: { ...SCALE.y, min: opts.minY, max: opts.maxY },
        },
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        ...opts.extra,
      },
    });
  }

  function bar(key, canvasId, labels, datasets, opts = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return;
    return create(key, ctx, {
      type: 'bar',
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: TOOLTIP },
        scales: {
          x: SCALE.x,
          y: { ...SCALE.y, beginAtZero: true, max: opts.maxY || 1 },
        },
      },
    });
  }

  function radar(key, canvasId, labels, data, color) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return;
    return create(key, ctx, {
      type: 'radar',
      data: {
        labels,
        datasets: [{
          label: 'Attention',
          data,
          backgroundColor: `${color}26`,
          borderColor: color,
          pointBackgroundColor: color,
          borderWidth: 2,
          pointRadius: 4,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          r: {
            beginAtZero: true, max: 1,
            grid: { color: 'rgba(255,255,255,0.06)' },
            ticks: { display: false },
            pointLabels: { color: '#8892b0', font: { size: 10 } },
          },
        },
      },
    });
  }

  return { applyDefaults, gradientFill, create, destroy, line, bar, radar, TOOLTIP, SCALE };
})();
