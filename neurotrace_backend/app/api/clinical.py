"""
app/api/clinical.py

Updated to pass imputer and feature_cols from the ModelRegistry
to predict_clinical() — matching the new clinical_service pipeline.
"""
import time
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.services.model_loader    import ModelRegistry
from app.services.clinical_service import (
    predict_clinical, parse_csv_upload, CLINICAL_FEATURES, CLINICAL_DEFAULTS
)
from app.utils.file_handler       import save_upload, cleanup
from app.utils.response           import success, error, prediction_response
from app.middleware.auth          import require_patient_or_doctor
from app.models                   import Prediction, Patient
from app                          import db

logger      = logging.getLogger(__name__)
clinical_bp = Blueprint("clinical", __name__)


@clinical_bp.post("/predict")
@jwt_required()
@require_patient_or_doctor
def predict():
    """
    POST /clinical/predict

    Formats:
      1. JSON body:    { "patient_id": "PT-001", "Age": 65, ... }
      2. Multipart:    'clinical_data' CSV file + optional 'patient_id' field
    """
    patient_id   = None
    input_data   = {}
    source       = "json"
    content_type = request.content_type or ""

    if "application/json" in content_type:
        body       = request.get_json(silent=True) or {}
        patient_id = body.pop("patient_id", None)
        input_data = body
        source     = "json"

    elif "multipart/form-data" in content_type or "clinical_data" in request.files:
        patient_id = request.form.get("patient_id")
        if "clinical_data" not in request.files:
            return error("Provide JSON body or 'clinical_data' CSV file", 400)
        try:
            csv_path   = save_upload(request.files["clinical_data"], "data")
            input_data = parse_csv_upload(csv_path)
            source     = "csv"
        except ValueError as exc:
            return error(str(exc), 422)
        finally:
            cleanup(csv_path)

    else:
        return error("Unsupported content type. Use application/json or multipart/form-data", 415)

    # ── Load all clinical artifacts ───────────────────────────
    model        = ModelRegistry.get("clinical")
    scaler       = ModelRegistry.get("clinical_scaler")
    imputer      = ModelRegistry.get("clinical_imputer")
    feature_cols = ModelRegistry.get("clinical_feature_cols")

    if model is None:
        return error("Clinical model not loaded on server", 503)

    # ── Predict ───────────────────────────────────────────────
    t0 = time.time()
    try:
        result = predict_clinical(
            input_data, model,
            scaler=scaler,
            imputer=imputer,
            feature_cols=feature_cols,
        )
        result["input_source"] = source
    except Exception as exc:
        logger.error("Clinical prediction error: %s", exc)
        return error(f"Prediction error: {exc}", 500)

    elapsed = int((time.time() - t0) * 1000)
    if patient_id:
        _persist_prediction(patient_id, "clinical", result)

    return prediction_response("clinical", result,
                               patient_id=patient_id, processing_ms=elapsed)


@clinical_bp.get("/features/schema")
def feature_schema():
    """GET /clinical/features/schema — feature list + defaults."""
    feature_cols = ModelRegistry.get("clinical_feature_cols")
    cols = list(feature_cols) if feature_cols is not None else list(CLINICAL_FEATURES)
    return success(data={
        "features":    cols,
        "count":       len(cols),
        "defaults":    CLINICAL_DEFAULTS,
        "description": "Clinical dataset feature columns. Missing fields will use defaults.",
    })


def _persist_prediction(patient_uid, modality, result):
    try:
        patient = Patient.query.filter_by(patient_uid=patient_uid).first()
        if not patient:
            return
        db.session.add(Prediction(
            patient_id = patient.id,
            modality   = modality,
            result     = result.get("probability"),
            label      = result.get("label"),
            severity   = result.get("severity"),
            confidence = result.get("confidence"),
            raw_output = result,
        ))
        db.session.commit()
    except Exception as exc:
        logger.error("Clinical persist failed: %s", exc)
        db.session.rollback()