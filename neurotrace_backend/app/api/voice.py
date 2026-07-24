"""
app/api/voice.py
Voice model prediction endpoints.

POST /voice/predict       — upload audio file → extract features → predict
POST /voice/features      — upload audio file → return features only (no prediction)
GET  /voice/features/schema — return expected feature column list
"""
import time
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.services.model_loader       import ModelRegistry
from app.services.voice_service      import predict_from_audio, extract_voice_features, VOICE_FEATURES
from app.utils.file_handler          import save_upload, cleanup
from app.utils.response              import success, error, prediction_response
from app.middleware.auth             import require_patient_or_doctor
from app.models                      import Prediction, Patient
from app                             import db

voice_bp = Blueprint("voice", __name__)


@voice_bp.post("/predict")
@jwt_required()
@require_patient_or_doctor
def predict():
    """
    POST /voice/predict
    Form-data:  audio (file), patient_id (str, optional)
    """
    if "audio" not in request.files:
        return error("'audio' file is required", 400)

    patient_id = request.form.get("patient_id")
    audio_file = request.files["audio"]

    # Save upload
    try:
        audio_path = save_upload(audio_file, "audio")
    except ValueError as exc:
        return error(str(exc), 400)

    # Check model availability
    model             = ModelRegistry.get("voice")
    scaler            = ModelRegistry.get("voice_scaler")
    selector          = ModelRegistry.get("voice_selector")
    selected_features = ModelRegistry.get("voice_selected_features")
    if model is None:
        cleanup(audio_path)
        return error("Voice model not loaded on server", 503)

    # Predict
    t0 = time.time()
    try:
        result = predict_from_audio(audio_path, model, scaler, selector, selected_features)
    except ValueError as exc:
        cleanup(audio_path)
        return error(f"Feature extraction failed: {exc}", 422)
    except Exception as exc:
        cleanup(audio_path)
        return error(f"Prediction error: {exc}", 500)
    finally:
        cleanup(audio_path)

    elapsed = int((time.time() - t0) * 1000)

    # Persist prediction if patient_id provided
    if patient_id:
        _persist_prediction(patient_id, "voice", result)
    
    from flask import current_app
    current_app.logger.info(f"Voice prediction for {patient_id}: {result}")

    return prediction_response("voice", result, patient_id=patient_id, processing_ms=elapsed)


@voice_bp.post("/features")
@jwt_required()
def extract_features_only():
    """
    POST /voice/features
    Returns extracted biomarker features without running the classifier.
    Useful for debugging and manual inspection.
    """
    if "audio" not in request.files:
        return error("'audio' file is required", 400)

    try:
        audio_path = save_upload(request.files["audio"], "audio")
        features   = extract_voice_features(audio_path)
    except ValueError as exc:
        return error(str(exc), 422)
    except Exception as exc:
        return error(f"Feature extraction error: {exc}", 500)
    finally:
        cleanup(audio_path)

    return success(data={"features": features, "feature_count": len(features)})


@voice_bp.get("/features/schema")
def feature_schema():
    """GET /voice/features/schema — list of expected voice feature columns."""
    return success(data={
        "features": VOICE_FEATURES,
        "count":    len(VOICE_FEATURES),
        "description": "Voice biomarker columns extracted from audio using Praat/librosa",
    })


# ── Internal helper ───────────────────────────────────────────
def _persist_prediction(patient_uid: str, modality: str, result: dict):
    """Save a prediction record to the database."""
    try:
        patient = Patient.query.filter_by(patient_uid=patient_uid).first()
        if not patient:
            return
        pred = Prediction(
            patient_id  = patient.id,
            modality    = modality,
            result      = result.get("probability"),
            label       = result.get("label"),
            severity    = result.get("severity"),
            confidence  = result.get("confidence"),
            raw_output  = result,
            input_meta  = {"source": "audio_upload"},
        )
        db.session.add(pred)
        db.session.commit()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Failed to persist prediction: %s", exc)
        db.session.rollback()