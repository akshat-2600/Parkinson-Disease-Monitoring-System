/* ============================================================
   js/components/gauge.js — SVG Severity Gauge
   ============================================================ */

const Gauge = (() => {

  const TOTAL_ARC = 251.2; // circumference of the half-circle path

  function template() {
    return `
      <div class="gauge-wrap">
        <svg class="gauge-svg" viewBox="0 0 200 110">
          <defs>
            <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stop-color="#00e5a0"/>
              <stop offset="50%"  stop-color="#ffb547"/>
              <stop offset="100%" stop-color="#ff4e6a"/>
            </linearGradient>
          </defs>
          <!-- Track -->
          <path d="M 20 100 A 80 80 0 0 1 180 100"
                fill="none" stroke="var(--bg-3)" stroke-width="14" stroke-linecap="round"/>
          <!-- Value arc -->
          <path id="gaugeArc"
                d="M 20 100 A 80 80 0 0 1 180 100"
                fill="none" stroke="url(#gaugeGrad)" stroke-width="14" stroke-linecap="round"
                stroke-dasharray="0 ${TOTAL_ARC}"
                style="transition: stroke-dasharray 1.2s ease"/>
          <!-- Needle -->
          <line id="gaugeNeedle"
                x1="100" y1="100" x2="100" y2="30"
                stroke="var(--text-1)" stroke-width="2" stroke-linecap="round"
                style="transform-origin:100px 100px; transition: transform 1.2s ease"/>
          <circle cx="100" cy="100" r="5" fill="var(--text-1)"/>
          <!-- Value text -->
          <text id="gaugeText" x="100" y="86"
                fill="var(--text-1)" font-family="Syne,sans-serif"
                font-weight="800" font-size="22" text-anchor="middle">—</text>
          <text x="100" y="98"
                fill="var(--text-3)" font-family="DM Mono,monospace"
                font-size="9" text-anchor="middle">SEVERITY INDEX</text>
          <!-- Range labels -->
          <text x="18"  y="115" fill="var(--text-3)" font-size="9" text-anchor="middle" font-family="DM Mono,monospace">0</text>
          <text x="182" y="115" fill="var(--text-3)" font-size="9" text-anchor="middle" font-family="DM Mono,monospace">100</text>
        </svg>
        <div class="gauge-stage text-amber" id="gaugeStageLabel">—</div>
      </div>`;
  }

  /**
   * Update the gauge arc, needle, and label.
   * @param {number} val   — severity 0–100
   * @param {string} stage — e.g. "Stage III"
   */
  function update(val, stage) {
    const pct = Helpers.clamp(val, 0, 100) / 100;

    const arc    = document.getElementById('gaugeArc');
    const needle = document.getElementById('gaugeNeedle');
    const text   = document.getElementById('gaugeText');
    const label  = document.getElementById('gaugeStageLabel');

    if (arc)    arc.style.strokeDasharray = `${pct * TOTAL_ARC} ${TOTAL_ARC}`;
    if (needle) needle.style.transform    = `rotate(${-90 + pct * 180}deg)`;
    if (text)   text.textContent          = val;
    if (label)  label.textContent         = stage || '—';
  }

  return { template, update };
})();
