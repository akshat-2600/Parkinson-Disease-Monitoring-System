"""
app/api/timeseries.py
Time-series progression model endpoint.

POST /timeseries/predict — CSV/JSON time-series data → progression prediction
"""
import time
import numpy as np
import pandas as pd
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.services.model_loader import ModelRegistry
from app.utils.file_handler    import save_upload, cleanup
from app.utils.response        import success, error, prediction_response
from app.middleware.auth       import require_patient_or_doctor
from app.models                import Prediction, Patient
from app                       import db

timeseries_bp = Blueprint("timeseries", __name__)


@timeseries_bp.post("/predict")
@jwt_required()
@require_patient_or_doctor
def predict():
    """
    POST /timeseries/predict
    Expects multipart with 'timeseries_data' CSV (rows = time steps, cols = features)
    OR JSON body: { "patient_id": "PT-001", "data": [[...], [...], ...] }
    """
    patient_id = None
    X          = None
    content_type = request.content_type or ""

    # ── JSON path ─────────────────────────────────────────────
    if "application/json" in content_type:
        body       = request.get_json(silent=True) or {}
        patient_id = body.pop("patient_id", None)
        raw_data   = body.get("data")
        if not raw_data:
            return error("'data' array is required in JSON body", 400)
        try:
            X = np.array(raw_data, dtype=np.float32)
        except Exception:
            return error("'data' must be a 2D numeric array", 422)

    # ── CSV upload path ───────────────────────────────────────
    elif "timeseries_data" in request.files:
        patient_id = request.form.get("patient_id")
        try:
            csv_path = save_upload(request.files["timeseries_data"], "data")
            df       = pd.read_csv(csv_path)
            X        = df.values.astype(np.float32)
        except Exception as exc:
            return error(f"CSV parsing failed: {exc}", 422)
        finally:
            cleanup(csv_path)
    else:
        return error("Provide JSON body with 'data' or 'timeseries_data' CSV file", 400)

    model = ModelRegistry.get("timeseries")
    if model is None:
        return error("Time-series model not loaded on server", 503)

    # Reshape: most time-series models expect (1, time_steps, features)
    if X.ndim == 1:
        X = X.reshape(1, -1, 1)
    elif X.ndim == 2:
        X = X.reshape(1, *X.shape)

    t0 = time.time()
    try:
        # Support sklearn (predict_proba) or Keras (predict)
        if hasattr(model, "predict_proba"):
            X_flat = X.reshape(1, -1)
            proba  = model.predict_proba(X_flat)[0]
            prob_pd = float(proba[1]) if len(proba) > 1 else float(proba[0])
        else:
            raw = model.predict(X, verbose=0)
            prob_pd = float(raw[0][0]) if raw.shape[-1] == 1 else float(raw[0][1])

        has_pd     = prob_pd >= 0.5
        confidence = prob_pd if has_pd else 1 - prob_pd
        result = {
            "has_parkinson": has_pd,
            "probability":   round(prob_pd, 4),
            "confidence":    round(confidence, 4),
            "severity":      round(prob_pd * 100, 2),
            "label":         "Parkinson's Detected" if has_pd else "No Parkinson's Detected",
            "time_steps":    X.shape[1],
            "features":      X.shape[2] if X.ndim == 3 else 1,
        }
    except Exception as exc:
        return error(f"Time-series prediction error: {exc}", 500)

    elapsed = int((time.time() - t0) * 1000)
    if patient_id:
        _persist(patient_id, "timeseries", result)

    return prediction_response("timeseries", result, patient_id=patient_id, processing_ms=elapsed)


def _persist(patient_uid, modality, result):
    try:
        patient = Patient.query.filter_by(patient_uid=patient_uid).first()
        if not patient:
            return
        db.session.add(Prediction(
            patient_id=patient.id, modality=modality,
            result=result.get("probability"), label=result.get("label"),
            severity=result.get("severity"), confidence=result.get("confidence"),
            raw_output=result,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()