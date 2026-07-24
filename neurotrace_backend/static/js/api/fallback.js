/* ============================================================
   js/api/fallback.js — Static fallback data (used when the
   Flask backend is unreachable)
   ============================================================ */

const Fallback = (() => {

  /* ── Patient roster ── */
  const PATIENTS = {
    'PT-001': {
      name: 'James Harrington', initials: 'JH', age: 67, gender: 'Male',
      diagnosis: "Parkinson's Disease", onset: '2019',
      severity: 62, stage: 'Stage III', updrs: 45,
      severity_change: 3.2, updrs_change: '+1.5',
      fusion_confidence: 0.87, status: 'warning',
      alerts: [
        { type: 'critical', msg: 'Tremor intensity elevated 40% from baseline',         time: '2h ago' },
        { type: 'warning',  msg: 'Medication window missed — Levodopa 14:00 dose',      time: '4h ago' },
        { type: 'info',     msg: 'Voice analysis shows 12% dysarthria progression',     time: '1d ago' },
      ],
      risks: [
        { name: 'Falls Risk',       level: 'high'   },
        { name: 'Dysarthria',       level: 'medium' },
        { name: 'Cognitive Decline',level: 'medium' },
        { name: 'Dysphagia',        level: 'low'    },
      ],
      modalities: { voice: 0.72, clinical: 0.85, timeseries: 0.68, mri: 0.90, spiral: 0.77, motor: 0.83 },
    },
    'PT-002': {
      name: 'Maria Chen', initials: 'MC', age: 58, gender: 'Female',
      diagnosis: "Parkinson's Disease", onset: '2021',
      severity: 38, stage: 'Stage II', updrs: 28,
      severity_change: 1.1, updrs_change: '–0.8',
      fusion_confidence: 0.92, status: 'stable',
      alerts: [
        { type: 'info', msg: 'Scheduled DBS follow-up due in 7 days', time: '5h ago' },
      ],
      risks: [
        { name: 'Falls Risk',         level: 'low'    },
        { name: 'Bradykinesia',       level: 'medium' },
        { name: 'Postural Instability',level: 'low'   },
      ],
      modalities: { voice: 0.81, clinical: 0.90, timeseries: 0.75, mri: 0.88, spiral: 0.84, motor: 0.78 },
    },
    'PT-003': {
      name: 'Robert Okafor', initials: 'RO', age: 72, gender: 'Male',
      diagnosis: "Parkinson's Disease", onset: '2016',
      severity: 78, stage: 'Stage IV', updrs: 61,
      severity_change: 5.8, updrs_change: '+4.2',
      fusion_confidence: 0.83, status: 'critical',
      alerts: [
        { type: 'critical', msg: 'Severe motor fluctuations — orthostatic hypotension risk', time: '30m ago' },
        { type: 'critical', msg: 'Cognitive assessment score declined 18% this month',        time: '3h ago' },
        { type: 'warning',  msg: 'Speech intelligibility below clinical threshold',           time: '6h ago' },
      ],
      risks: [
        { name: 'Falls Risk',             level: 'high'   },
        { name: 'Dementia Risk',          level: 'high'   },
        { name: 'Dysphagia',              level: 'medium' },
        { name: 'Orthostatic Hypotension',level: 'high'   },
      ],
      modalities: { voice: 0.55, clinical: 0.79, timeseries: 0.62, mri: 0.85, spiral: 0.58, motor: 0.71 },
    },
    'PT-004': {
      name: 'Susan Patel', initials: 'SP', age: 63, gender: 'Female',
      diagnosis: "Parkinson's Disease", onset: '2020',
      severity: 48, stage: 'Stage II', updrs: 34,
      severity_change: 1.9, updrs_change: '+0.5',
      fusion_confidence: 0.89, status: 'stable',
      alerts: [
        { type: 'info', msg: 'Physical therapy session scheduled tomorrow', time: '1d ago' },
      ],
      risks: [
        { name: 'Falls Risk',     level: 'medium' },
        { name: 'Fatigue',        level: 'medium' },
        { name: 'Depression Screen', level: 'low' },
      ],
      modalities: { voice: 0.78, clinical: 0.88, timeseries: 0.72, mri: 0.91, spiral: 0.80, motor: 0.85 },
    },
  };

  function getDashboard(pid) {
    return PATIENTS[pid] || PATIENTS['PT-001'];
  }

  /* ── History ── */
  function getHistory(pid) {
    const now   = Date.now();
    const labels = Array.from({ length: 12 }, (_, i) => {
      const d = new Date(now - (11 - i) * 30 * 24 * 3600 * 1000);
      return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
    });
    const base  = pid === 'PT-003' ? 62 : pid === 'PT-001' ? 47 : pid === 'PT-004' ? 35 : 28;
    const noise = () => (Math.random() - 0.4) * 4;
    return {
      labels,
      severity:      labels.map((_, i) => Math.min(100, base + i * 1.4 + noise())),
      updrs:         labels.map((_, i) => Math.min(120, base * 0.7 + i * 1.1 + noise())),
      voice:         labels.map(() => parseFloat((0.5 + Math.random() * 0.4).toFixed(2))),
      mri:           labels.map(() => parseFloat((0.6 + Math.random() * 0.35).toFixed(2))),
      motor:         labels.map(() => parseFloat((0.55 + Math.random() * 0.38).toFixed(2))),
      interventions: [
        { date: labels[2],  event: 'Levodopa dosage adjusted +50 mg' },
        { date: labels[5],  event: 'Physical therapy programme initiated' },
        { date: labels[8],  event: 'Speech–language therapy assessment' },
        { date: labels[10], event: 'DBS pre-evaluation screening completed' },
      ],
    };
  }

  /* ── Explanation ── */
  function getExplanation() {
    return {
      features: [
        { name: 'Gait Asymmetry',      importance: 0.82 },
        { name: 'Tremor Freq (Hz)',     importance: 0.76 },
        { name: 'MRI Putamen Vol.',     importance: 0.71 },
        { name: 'Voice Jitter',         importance: 0.68 },
        { name: 'Spiral Regularity',   importance: 0.63 },
        { name: 'Finger Tapping Rate', importance: 0.59 },
        { name: 'UPDRS Motor III',      importance: 0.55 },
        { name: 'Cognitive Screen',     importance: 0.48 },
        { name: 'Postural Sway',        importance: 0.44 },
        { name: 'Drug Response',        importance: 0.38 },
      ],
      attention: [0.92, 0.45, 0.67, 0.83, 0.29, 0.71, 0.88, 0.52],
      summary: `The fusion model identified <strong>Gait Asymmetry</strong> and
        <strong>Tremor Frequency</strong> as the most influential predictors, contributing
        82 % and 76 % importance respectively. MRI volumetric analysis of the substantia
        nigra and putamen showed statistically significant dopaminergic neuron loss consistent
        with the stated staging. Voice biomarker analysis revealed elevated jitter (2.3 %) and
        shimmer (4.1 %) exceeding clinical thresholds. The spiral drawing model detected
        irregular angular velocity patterns with 68 % deviation from normative curves.
        Multi-modal fusion confidence stands at 87 %, indicating high-reliability prediction.`,
    };
  }

  /* ── Recommendations ── */
  function getRecommendations() {
    return [
      { title: 'Immediate Levodopa Titration Review', priority: 'high', category: 'Pharmacotherapy', confidence: 0.91, reasoning: 'Current motor fluctuation pattern and wearing-off episodes suggest suboptimal carbidopa/levodopa timing. Consider fractionating daily dose or adding a COMT inhibitor adjunct.' },
      { title: 'Urgent Falls Prevention Protocol',    priority: 'high', category: 'Safety',          confidence: 0.88, reasoning: 'Postural instability index has crossed clinical threshold (score 3.2/5). Immediate home safety assessment and physiotherapy referral are critical to prevent injurious falls.' },
      { title: 'Speech–Language Pathology Referral',  priority: 'moderate', category: 'Rehabilitation', confidence: 0.79, reasoning: 'Voice analysis shows 12 % progression in dysarthria markers. Early LSVT LOUD therapy intervention has demonstrated 80 % efficacy at similar staging.' },
      { title: 'Cognitive Screening Battery',         priority: 'moderate', category: 'Neuropsychology', confidence: 0.74, reasoning: 'MRI hippocampal volume trends and baseline cognitive assessment suggest borderline MCI risk. Comprehensive neuropsychological evaluation recommended within 30 days.' },
      { title: 'Structured Aerobic Exercise Program', priority: 'preventive', category: 'Lifestyle',  confidence: 0.85, reasoning: 'Evidence-based protocols (150 min/week moderate intensity) have neuroprotective effects in PD. Treadmill training with cueing improves gait by 15–20 %.' },
      { title: 'Mediterranean Diet Optimisation',     priority: 'preventive', category: 'Nutrition',  confidence: 0.71, reasoning: 'High antioxidant, omega-3-rich, low glycaemic-index diets are associated with slower dopaminergic decline. Refer to neurological dietitian.' },
    ];
  }

  return { getDashboard, getHistory, getExplanation, getRecommendations };
})();
