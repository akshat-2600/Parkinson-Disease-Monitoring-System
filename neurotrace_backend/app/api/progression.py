"""
app/api/progression.py
─────────────────────────────────────────────────────────────
New API endpoints for:
  GET /progression/forecast/<patient_id>     — future severity prediction
  GET /progression/baseline/<patient_id>     — patient-specific baseline
  GET /progression/lime/<patient_id>/<modality> — LIME explanation
  GET /progression/summary/<patient_id>      — full personalized report

Register in app/__init__.py:
  from app.api.progression import progression_bp
  app.register_blueprint(progression_bp, url_prefix="/api/progression")
"""
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.middleware.auth             import require_patient_or_doctor
from app.models                      import Patient, Prediction
from app.utils.response              import success, error
from app.services.progression_service import (
    forecast_progression, compute_patient_baseline,
    lime_explain_clinical, lime_explain_voice,
)
from app.services.model_loader       import ModelRegistry

logger        = logging.getLogger(__name__)
progression_bp = Blueprint("progression", __name__)


# ─────────────────────────────────────────────────────────────
# GET /progression/forecast/<patient_id>
# ─────────────────────────────────────────────────────────────
@progression_bp.get("/forecast/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def forecast(patient_id):
    """
    Predict future severity using the patient's own stored history.
    Satisfies Objective 4: Holistic PD Severity & Progression Prediction.
    """
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    # Use fusion predictions primarily; fall back to any modality
    preds = (Prediction.query
             .filter_by(patient_id=patient.id, modality="fusion")
             .order_by(Prediction.created_at.asc()).all())

    if len(preds) < 2:
        # Try all modalities with severity
        preds = (Prediction.query
                 .filter(Prediction.patient_id == patient.id,
                         Prediction.severity != None)
                 .order_by(Prediction.created_at.asc()).all())

    horizon = request.args.get("horizon_days", 90, type=int)
    result  = forecast_progression(preds, horizon_days=horizon)
    return success(data=result)


# ─────────────────────────────────────────────────────────────
# GET /progression/baseline/<patient_id>
# ─────────────────────────────────────────────────────────────
@progression_bp.get("/baseline/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def baseline(patient_id):
    """
    Compute patient-specific baseline severity.
    Satisfies Objective 3: Personalized Progression Modeling.
    Module 4: Patient-Specific Adaptation.
    """
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    preds = (Prediction.query
             .filter_by(patient_id=patient.id)
             .order_by(Prediction.created_at.asc()).all())

    result = compute_patient_baseline(preds)
    return success(data=result)


# ─────────────────────────────────────────────────────────────
# GET /progression/lime/<patient_id>/<modality>
# ─────────────────────────────────────────────────────────────
@progression_bp.get("/lime/<patient_id>/<modality>")
@jwt_required()
@require_patient_or_doctor
def lime_explanation(patient_id, modality):
    """
    LIME explanation for the latest prediction of a given modality.
    Satisfies Module 3: Explainable Severity and Progression Modeling.
    """
    if modality not in ("clinical", "voice"):
        return error("LIME supported for: clinical, voice", 400)

    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    pred = (Prediction.query
            .filter_by(patient_id=patient.id, modality=modality)
            .order_by(Prediction.created_at.desc()).first())

    if not pred or not pred.raw_output:
        return success(data={
            "success": False,
            "reason":  f"No {modality} prediction found for this patient. Run a {modality} prediction first.",
        })

    raw_features = pred.raw_output.get("features") or pred.raw_output

    if modality == "clinical":
        from app.services.clinical_service import CLINICAL_FEATURES
        model  = ModelRegistry.get("clinical")
        scaler = ModelRegistry.get("clinical_scaler")
        if not model:
            return error("Clinical model not loaded", 503)
        result = lime_explain_clinical(model, scaler, raw_features, CLINICAL_FEATURES)

    else:  # voice
        from app.services.voice_service import VOICE_FEATURES
        model  = ModelRegistry.get("voice")
        scaler = ModelRegistry.get("voice_scaler")
        if not model:
            return error("Voice model not loaded", 503)
        result = lime_explain_voice(model, scaler, raw_features, VOICE_FEATURES)

    return success(data=result)


# ─────────────────────────────────────────────────────────────
# GET /progression/summary/<patient_id>
# ─────────────────────────────────────────────────────────────
@progression_bp.get("/summary/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def summary(patient_id):
    """
    Full personalized progression summary combining:
    - Patient-specific baseline
    - Forecasting
    - Adaptation status
    All in one call for the frontend dashboard.
    """
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    all_preds = (Prediction.query
                 .filter_by(patient_id=patient.id)
                 .order_by(Prediction.created_at.asc()).all())

    fusion_preds = [p for p in all_preds if p.modality == "fusion"]
    sev_preds    = fusion_preds if fusion_preds else [p for p in all_preds if p.severity is not None]

    baseline_data = compute_patient_baseline(all_preds)
    forecast_data = forecast_progression(sev_preds, horizon_days=90)

    return success(data={
        "patient_uid":   patient_id,
        "baseline":      baseline_data,
        "forecast":      forecast_data,
        "total_predictions": len(all_preds),
    })