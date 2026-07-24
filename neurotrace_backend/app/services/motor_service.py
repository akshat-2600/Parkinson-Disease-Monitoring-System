"""
app/services/motor_service.py

Updated to use the new model artifacts:
  - BEST_motor.pkl       → fitted Gaussian Naive Bayes (96.15%)
  - scaler_motor.pkl     → StandardScaler
  - imputer_motor.pkl    → SimpleImputer(strategy='median')
  - label_encoder_motor.pkl → LabelEncoder (classes: HC, PD, RBD)
  - motor_feature_cols.pkl  → list[str] of 63 feature names

Prediction pipeline (matches training notebook):
  input_dict → DataFrame(motor_feature_cols) → imputer → scaler → model.predict_proba
"""
import numpy as np
import pandas as pd
import logging
import re

logger = logging.getLogger(__name__)

# ── Fallback feature list (used only when motor_feature_cols.pkl absent) ──
MOTOR_FEATURES = [
    "age_years", "gender",
    "positive_history_of_parkinson_disease_in_family",
    "age_of_disease_onset_years",
    "duration_of_disease_from_first_symptoms_years",
    "antidepressant_therapy", "antiparkinsonian_medication",
    "antipsychotic_medication", "benzodiazepine_medication",
    "levodopa_equivalent_mg_day",
    # UPDRS III items
    "18._speech", "19._facial_expression",
    "20._tremor_at_rest_-_head",
    "20._tremor_at_rest_-_rue", "20._tremor_at_rest_-_lue",
    "20._tremor_at_rest_-_rle", "20._tremor_at_rest_-_lle",
    "21._action_or_postural_tremor_-_rue", "21._action_or_postural_tremor_-_lue",
    "22._rigidity_-_neck",
    "22._rigidity_-_rue", "22._rigidity_-_lue",
    "22._rigidity_-_rle", "22._rigidity_-_lle",
    "23.finger_taps_-_rue", "23.finger_taps_-_lue",
    "24._hand_movements_-_rue", "24._hand_movements_-_lue",
    "25._rapid_alternating_movements_-_rue", "25._rapid_alternating_movements_-_lue",
    "26._leg_agility_-_rle", "26._leg_agility_-_lle",
    "27._arising_from_chair", "28._posture", "29._gait",
    "30._postural_stability", "31._body_bradykinesia_and_hypokinesia",
]

MOTOR_DEFAULTS: dict = {col: 0.0 for col in MOTOR_FEATURES}
MOTOR_DEFAULTS.update({
    "age_years": 65,
    "levodopa_equivalent_mg_day": 300,
})


def _canonical(name: str) -> str:
    """Lowercase + collapse whitespace + normalise special chars."""
    s = str(name).replace("‰", "permille").replace("‰", "permille")
    s = re.sub(r"[\s\(\)\-\/\,\.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    s = str(value).strip().lower()
    if s in {"", "nan", "none", "null"}:
        return float(default)
    if s in {"m", "male", "true", "yes", "y"}:
        return 1.0
    if s in {"f", "female", "false", "no", "n"}:
        return 0.0
    try:
        return float(s)
    except Exception:
        return float(default)


def _build_row(input_data: dict, expected_cols: list) -> pd.DataFrame:
    """
    Build a single-row DataFrame with exactly expected_cols.
    Uses canonical name matching so API field names map to training column names.
    Input keys and expected_cols are both canonicalised for matching.
    """
    input_alias = {_canonical(k): v for k, v in input_data.items()}
    row = {}
    for col in expected_cols:
        key = _canonical(col)
        val = input_alias.get(key, 0.0)
        row[col] = _to_float(val)
    return pd.DataFrame([row], columns=expected_cols)


def predict_motor(input_data: dict, model, scaler=None,
                  imputer=None, encoder=None, feature_cols=None) -> dict:
    """
    Motor data dict → prediction.

    Pipeline:
      build_row(feature_cols) → imputer.transform → scaler.transform → model.predict_proba

    Args:
        input_data:   dict of motor feature values (partial OK — missing → 0.0)
        model:        BEST_motor.pkl (Naive Bayes)
        scaler:       scaler_motor.pkl
        imputer:      imputer_motor.pkl (SimpleImputer)
        encoder:      label_encoder_motor.pkl (LabelEncoder; classes: HC, PD, RBD)
        feature_cols: motor_feature_cols.pkl (list[str])

    Returns dict with: has_parkinson, probability, confidence, severity, label
    """
    # ── Determine feature column order ────────────────────────
    if feature_cols is not None:
        expected_cols = list(feature_cols)
    elif scaler is not None and hasattr(scaler, "feature_names_in_"):
        expected_cols = list(scaler.feature_names_in_)
    elif hasattr(model, "feature_names_in_"):
        expected_cols = list(model.feature_names_in_)
    else:
        expected_cols = list(MOTOR_FEATURES)
        logger.warning("motor_feature_cols not available — using fallback list (%d cols)", len(expected_cols))

    # ── Build DataFrame ───────────────────────────────────────
    X_df = _build_row(input_data, expected_cols)

    missing = [c for c in expected_cols if _canonical(c) not in {_canonical(k) for k in input_data}]
    if missing:
        logger.info("Motor: %d fields defaulted to 0: %s", len(missing), missing[:5])

    # ── Impute → Scale → Predict ──────────────────────────────
    X = X_df.values.astype(np.float64)

    if imputer is not None:
        try:
            X = imputer.transform(X)
        except Exception as exc:
            logger.warning("Motor imputer failed: %s — skipping", exc)

    if scaler is not None:
        try:
            X = scaler.transform(X)
        except Exception as exc:
            logger.warning("Motor scaler failed: %s — using unscaled", exc)

    proba     = model.predict_proba(X)[0]
    label_idx = int(np.argmax(proba))

    # Map back to class labels
    if encoder is not None:
        classes = list(encoder.classes_)
    else:
        # Fallback: assume order matches model.classes_
        classes = [str(c) for c in getattr(model, "classes_", ["HC", "PD", "RBD"])]

    # Find P(PD)
    pd_idx = classes.index("PD") if "PD" in classes else (1 if len(classes) > 1 else 0)
    prob_pd = float(proba[pd_idx]) if pd_idx < len(proba) else float(proba[label_idx])

    has_pd     = label_idx == pd_idx
    confidence = float(proba[label_idx])

    return {
        "has_parkinson":      has_pd,
        "probability":        prob_pd,
        "confidence":         confidence,
        "severity":           round(prob_pd * 100, 2),
        "label":              "Parkinson's Detected" if has_pd else "No Parkinson's Detected",
        "predicted_class":    classes[label_idx] if label_idx < len(classes) else str(label_idx),
        "class_probabilities": dict(zip(classes, [round(float(p), 4) for p in proba])),
        "hoehn_yahr_est":     _estimate_hoehn_yahr(input_data),
        "missing_fields":     missing,
    }


def _estimate_hoehn_yahr(data: dict) -> float:
    """Rough Hoehn & Yahr estimate from UPDRS sub-items."""
    get = lambda k: _to_float(data.get(k, data.get(_canonical(k), 0)))
    updrs = sum([
        get("20. Tremor at Rest - RUE"),
        get("20. Tremor at Rest - LUE"),
        get("28. Posture"),
        get("29. Gait"),
        get("30. Postural Stability"),
    ])
    if updrs <= 2:  return 1.0
    if updrs <= 5:  return 1.5
    if updrs <= 8:  return 2.0
    if updrs <= 12: return 2.5
    if updrs <= 18: return 3.0
    if updrs <= 24: return 4.0
    return 5.0


def parse_motor_csv(file_path: str) -> dict:
    """Parse a motor CSV file → dict (first data row)."""
    df = pd.read_csv(file_path)
    # Drop ID / target columns if present
    drop_cols = [c for c in df.columns if any(
        kw in c.lower() for kw in ["participant", "id", "updrs_iii_total", "hoehn"]
    )]
    df = df.drop(columns=drop_cols, errors="ignore")
    # Collapse duplicate spaces in column names
    df.columns = [" ".join(c.split()) for c in df.columns]
    if df.empty:
        raise ValueError("Motor CSV contains no data rows")
    return df.iloc[0].to_dict()