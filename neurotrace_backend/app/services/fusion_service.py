"""
app/services/fusion_service.py

Multi-modal fusion engine updated to match the training notebook's
LightGBM stacker (AUC 0.9456) which expects:
  feature vector = [spiral_prob, mri_prob, voice_prob, motor_prob, clinical_prob]
  — scaled with meta_scaler before being passed to the LightGBM stacker.

Strategy:
  1. Run whichever modality models have valid inputs.
  2. If fusion model + meta_scaler loaded → use LightGBM stacker.
  3. Else → weighted soft-voting ensemble across available modalities.
"""
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Modality weights for soft-voting fallback ─────────────────
MODALITY_WEIGHTS = {
    "voice":      0.18,
    "clinical":   0.22,
    "mri":        0.25,
    "spiral":     0.12,
    "motor":      0.15,
    "timeseries": 0.08,
}

# ── Ordered modalities matching the training feature vector ───
# The fusion meta-learner was trained with:
#   [spiral_prob, mri_prob, voice_prob, motor_prob, clinical_prob]
# (resample-aligned on clinical dataset, motor=0.5 missing value)
FUSION_MODAL_ORDER = ["spiral", "mri", "voice", "motor", "clinical"]

MISSING_PROB = 0.5   # neutral probability for absent modality

SEVERITY_STAGES = [
    (0,  20, "Stage 0 — No Evidence"),
    (20, 35, "Stage I — Mild"),
    (35, 55, "Stage II — Moderate"),
    (55, 70, "Stage III — Moderate-Severe"),
    (70, 85, "Stage IV — Severe"),
    (85, 101, "Stage V — Critical"),
]


def severity_to_stage(severity: float) -> str:
    for lo, hi, label in SEVERITY_STAGES:
        if lo <= severity < hi:
            return label
    return "Unknown"


def fuse_predictions(modality_results: dict, fusion_model=None,
                     meta_scaler=None) -> dict:
    """
    Build fused prediction from per-modality result dicts.

    Args:
        modality_results: {modality_name: result_dict, ...}
            Each result_dict must have at least 'probability' and 'confidence'.
        fusion_model:     LightGBM stacker (may be None)
        meta_scaler:      StandardScaler for the 5-d meta-feature vector (may be None)

    Returns unified prediction dict.
    """
    if not modality_results:
        raise ValueError("No modality results provided for fusion")

    available = {k: v for k, v in modality_results.items() if v is not None}

    # ── Path 1: LightGBM stacker ─────────────────────────────
    if fusion_model is not None:
        try:
            feature_vec = _build_fusion_feature_vector(available)
            if meta_scaler is not None:
                feature_vec = meta_scaler.transform(feature_vec)
            proba      = fusion_model.predict_proba(feature_vec)[0]
            prob_pd    = float(proba[1]) if len(proba) > 1 else float(proba[0])
            confidence = float(max(proba))
            method     = "lgbm_stacker"
        except Exception as exc:
            logger.warning("Fusion stacker failed (%s) — falling back to ensemble", exc)
            prob_pd, confidence, method = _ensemble_vote(available)
    else:
        prob_pd, confidence, method = _ensemble_vote(available)

    # ── Derived metrics ───────────────────────────────────────
    has_pd   = prob_pd >= 0.5
    severity = round(prob_pd * 100, 2)
    stage    = severity_to_stage(severity)
    contrib  = _compute_contributions(available)

    return {
        "has_parkinson":          has_pd,
        "probability":            round(prob_pd, 4),
        "confidence":             round(confidence, 4),
        "severity":               severity,
        "stage":                  stage,
        "label":                  "Parkinson's Detected" if has_pd else "No Parkinson's Detected",
        "fusion_method":          method,
        "modalities_used":        list(available.keys()),
        "modality_contributions": contrib,
        "individual_results":     {k: _slim(v) for k, v in available.items()},
    }


def _build_fusion_feature_vector(available: dict) -> np.ndarray:
    """
    Build the 5-dimensional probability vector expected by the LightGBM stacker.
    Order: [spiral, mri, voice, motor, clinical]
    Missing modalities use MISSING_PROB (0.5 = neutral).
    Matches the fusion training matrix construction in the notebook.
    """
    row = []
    for mod in FUSION_MODAL_ORDER:
        if mod in available and available[mod] is not None:
            row.append(float(available[mod].get("probability", MISSING_PROB)))
        else:
            row.append(MISSING_PROB)
    return np.array([row], dtype=np.float64)


def _ensemble_vote(available: dict) -> tuple:
    """Weighted soft-voting fallback across available modalities."""
    total_weight  = 0.0
    weighted_prob = 0.0
    for mod, result in available.items():
        w    = MODALITY_WEIGHTS.get(mod, 0.10)
        prob = result.get("probability", MISSING_PROB)
        weighted_prob += w * float(prob)
        total_weight  += w

    if total_weight == 0:
        return MISSING_PROB, MISSING_PROB, "ensemble"

    prob_pd    = weighted_prob / total_weight
    conf_vals  = [float(r.get("confidence", MISSING_PROB)) for r in available.values()]
    base_conf  = float(np.mean(conf_vals))
    n_bonus    = min(0.15, (len(available) - 1) * 0.03)
    confidence = min(0.99, base_conf + n_bonus)
    return float(prob_pd), float(confidence), "weighted_ensemble"


def _slim(result: dict) -> dict:
    return {k: result.get(k) for k in ("probability", "confidence", "severity", "label")}


def _compute_contributions(available: dict) -> dict:
    total = sum(MODALITY_WEIGHTS.get(k, 0.10) for k in available)
    if total == 0:
        return {}
    return {
        k: round(MODALITY_WEIGHTS.get(k, 0.10) / total * 100, 1)
        for k in available
    }


# ──────────────────────────────────────────────────────────────
# Risk flags + recommendations (unchanged from original)
# ──────────────────────────────────────────────────────────────

def generate_risk_flags(fused: dict, individual: dict) -> list:
    flags    = []
    severity = fused.get("severity", 0)

    if severity >= 70:
        flags.append({"type": "critical", "msg": "Severity ≥ 70 — urgent clinical review required"})
    elif severity >= 50:
        flags.append({"type": "warning",  "msg": "Moderate–severe staging detected — schedule follow-up"})

    voice = individual.get("voice", {})
    if voice and voice.get("probability", 0) >= 0.75:
        flags.append({"type": "warning",  "msg": "Voice biomarkers indicate significant dysarthria"})

    mri = individual.get("mri", {})
    if mri and mri.get("probability", 0) >= 0.80:
        flags.append({"type": "critical", "msg": "MRI shows high probability of dopaminergic loss"})

    return flags


def generate_recommendations(fused: dict) -> list:
    severity = fused.get("severity", 0)
    recs = []

    if severity >= 70:
        recs.append({"priority": "high", "title": "Urgent Specialist Referral",
                     "category": "Clinical", "confidence": 0.95,
                     "reasoning": "Severity index exceeds 70%. Immediate neurology review recommended."})
        recs.append({"priority": "high", "title": "Falls Prevention Protocol",
                     "category": "Safety", "confidence": 0.90,
                     "reasoning": "High severity correlates with postural instability and fall risk."})

    if severity >= 40:
        recs.append({"priority": "moderate", "title": "Medication Timing Review",
                     "category": "Pharmacotherapy", "confidence": 0.82,
                     "reasoning": "Motor fluctuation pattern suggests sub-optimal levodopa scheduling."})
        recs.append({"priority": "moderate", "title": "Speech–Language Therapy",
                     "category": "Rehabilitation", "confidence": 0.78,
                     "reasoning": "Voice biomarkers indicate early dysarthria — LSVT LOUD recommended."})

    recs.append({"priority": "preventive", "title": "Structured Exercise Programme",
                 "category": "Lifestyle", "confidence": 0.85,
                 "reasoning": "150 min/week aerobic exercise shown to slow dopaminergic decline."})
    recs.append({"priority": "preventive", "title": "Mediterranean Diet",
                 "category": "Nutrition", "confidence": 0.72,
                 "reasoning": "Antioxidant-rich diet associated with slower neurodegeneration."})

    return recs