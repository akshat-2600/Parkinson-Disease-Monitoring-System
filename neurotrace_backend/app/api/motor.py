"""
app/api/motor.py

Updated to pass imputer, encoder, and feature_cols from the ModelRegistry
to predict_motor() — matching the new motor_service pipeline.
"""
import time
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.services.model_loader  import ModelRegistry
from app.services.motor_service import (
    predict_motor, parse_motor_csv, MOTOR_FEATURES, MOTOR_DEFAULTS
)
from app.utils.file_handler     import save_upload, cleanup
from app.utils.response         import success, error, prediction_response
from app.middleware.auth        import require_patient_or_doctor
from app.models                 import Prediction, Patient
from app                        import db

logger   = logging.getLogger(__name__)
motor_bp = Blueprint("motor", __name__)


@motor_bp.post("/predict")
@jwt_required()
@require_patient_or_doctor
def predict():
    """
    POST /motor/predict
    Accepts JSON body or multipart with 'motor_data' CSV file.
    """
    patient_id   = None
    input_data   = {}
    source       = "json"
    content_type = request.content_type or ""

    if "application/json" in content_type:
        body       = request.get_json(silent=True) or {}
        patient_id = body.pop("patient_id", None)
        input_data = body

    elif "motor_data" in request.files:
        patient_id = request.form.get("patient_id")
        try:
            csv_path   = save_upload(request.files["motor_data"], "data")
            input_data = parse_motor_csv(csv_path)
            source     = "csv"
        except ValueError as exc:
            return error(str(exc), 422)
        finally:
            cleanup(csv_path)

    else:
        return error("Provide JSON body or 'motor_data' CSV file", 400)

    # ── Load all motor artifacts ──────────────────────────────
    model        = ModelRegistry.get("motor")
    scaler       = ModelRegistry.get("motor_scaler")
    imputer      = ModelRegistry.get("motor_imputer")
    encoder      = ModelRegistry.get("motor_encoder")
    feature_cols = ModelRegistry.get("motor_feature_cols")

    if model is None:
        return error("Motor model not loaded on server", 503)

    # ── Predict ───────────────────────────────────────────────
    t0 = time.time()
    try:
        result = predict_motor(
            input_data, model,
            scaler=scaler,
            imputer=imputer,
            encoder=encoder,
            feature_cols=feature_cols,
        )
        result["input_source"] = source
    except Exception as exc:
        logger.error("Motor prediction error: %s", exc)
        return error(f"Motor prediction error: {exc}", 500)

    elapsed = int((time.time() - t0) * 1000)
    if patient_id:
        _persist(patient_id, "motor", result)

    return prediction_response("motor", result,
                               patient_id=patient_id, processing_ms=elapsed)


@motor_bp.get("/features/schema")
def feature_schema():
    """GET /motor/features/schema — feature column list + defaults."""
    # Use actual loaded cols if available
    feature_cols = ModelRegistry.get("motor_feature_cols")
    cols = list(feature_cols) if feature_cols is not None else list(MOTOR_FEATURES)
    return success(data={
        "features":    cols,
        "count":       len(cols),
        "defaults":    MOTOR_DEFAULTS,
        "description": "Motor examination feature columns (cleaned snake_case from training notebook)",
    })


def _persist(patient_uid, modality, result):
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
        logger.error("Motor persist failed: %s", exc)
        db.session.rollback()