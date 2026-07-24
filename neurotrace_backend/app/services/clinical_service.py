"""
app/services/clinical_service.py
Clinical structured data → prediction.

Handles the clinical dataset columns. Supports both full-column
submissions and partial submissions (fills missing with column means).
"""
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ── All feature columns from the clinical dataset ────────────
CLINICAL_FEATURES = [
    "Age", "Gender", "Ethnicity", "EducationLevel", "BMI",
    "Smoking", "AlcoholConsumption", "PhysicalActivity",
    "DietQuality", "SleepQuality",
    "FamilyHistoryParkinsons", "TraumaticBrainInjury",
    "Hypertension", "Diabetes", "Depression", "Stroke",
    "SystolicBP", "DiastolicBP",
    "CholesterolTotal", "CholesterolLDL", "CholesterolHDL", "CholesterolTriglycerides",
    "UPDRS", "MoCA", "FunctionalAssessment",
    "Tremor", "Rigidity", "Bradykinesia", "PosturalInstability",
    "SpeechProblems", "SleepDisorders", "Constipation",
]

# Sensible column defaults (approximate dataset means / modes)
CLINICAL_DEFAULTS = {
    "Age": 65, "Gender": 0, "Ethnicity": 0, "EducationLevel": 1, "BMI": 27.0,
    "Smoking": 0, "AlcoholConsumption": 2.5, "PhysicalActivity": 2.0,
    "DietQuality": 5.0, "SleepQuality": 6.0,
    "FamilyHistoryParkinsons": 0, "TraumaticBrainInjury": 0,
    "Hypertension": 0, "Diabetes": 0, "Depression": 0, "Stroke": 0,
    "SystolicBP": 120, "DiastolicBP": 80,
    "CholesterolTotal": 200, "CholesterolLDL": 130, "CholesterolHDL": 50,
    "CholesterolTriglycerides": 150,
    "UPDRS": 20, "MoCA": 25, "FunctionalAssessment": 3.0,
    "Tremor": 0, "Rigidity": 0, "Bradykinesia": 0, "PosturalInstability": 0,
    "SpeechProblems": 0, "SleepDisorders": 0, "Constipation": 0,
}


def build_feature_vector(input_data: dict) -> pd.DataFrame:
    """
    Build a feature vector from a (possibly partial) dict of clinical values.
    Missing fields are filled with CLINICAL_DEFAULTS.
    """
    row = {}
    for col in CLINICAL_FEATURES:
        val = input_data.get(col, CLINICAL_DEFAULTS.get(col, 0))
        row[col] = float(val)
    return pd.DataFrame([row], columns=CLINICAL_FEATURES)


def predict_clinical(input_data: dict, model, scaler=None) -> dict:
    """
    Clinical data dict → model prediction.
    Returns probability, label, severity.
    """
    X_df = build_feature_vector(input_data)
    missing = [c for c in CLINICAL_FEATURES if c not in input_data]
    if missing:
        logger.info("Clinical prediction: %d columns filled with defaults: %s", len(missing), missing)

    if scaler is not None:
        X = scaler.transform(X_df)
    else:
        # Some model types can consume a DataFrame directly, but ndarray is a safer fallback.
        X = X_df.values

    proba = model.predict_proba(X)[0]
    label_idx  = int(np.argmax(proba))
    confidence = float(proba[label_idx])
    has_pd     = bool(label_idx == 1)

    return {
        "has_parkinson":      has_pd,
        "probability":        float(proba[1]) if len(proba) > 1 else confidence,
        "confidence":         confidence,
        "severity":           round(float(proba[1]) * 100, 2) if len(proba) > 1 else round(confidence * 100, 2),
        "label":              "Parkinson's Detected" if has_pd else "No Parkinson's Detected",
        "updrs":              float(input_data.get("UPDRS", 0)),
        "moca":               float(input_data.get("MoCA", 0)),
        "missing_fields":     missing,
        "input_feature_count": len([c for c in CLINICAL_FEATURES if c in input_data]),
    }


def parse_csv_upload(file_path: str) -> dict:
    """Parse a single-row CSV upload into a dict of clinical values."""
    df = pd.read_csv(file_path)
    # Drop ID columns if present
    drop_cols = ["PatientID", "DoctorInCharge", "Diagnosis"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
    if df.empty:
        raise ValueError("CSV file contains no data rows")
    return df.iloc[0].to_dict()