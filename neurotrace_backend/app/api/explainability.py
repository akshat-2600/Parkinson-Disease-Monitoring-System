"""
app/api/explainability.py
Standalone explainability endpoints for any modality model.

POST /explain/shap/<modality>  — SHAP explanation for tabular models
POST /explain/lime/<modality>  — LIME explanation for tabular models
POST /explain/gradcam          — Grad-CAM heatmap for CNN models
GET  /explain/fusion/<patient_id> — full multi-modal explanation
"""
import logging
import numpy as np
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.services.model_loader          import ModelRegistry
from app.services.voice_service         import VOICE_FEATURES
from app.services.clinical_service      import CLINICAL_FEATURES
from app.services.motor_service         import MOTOR_FEATURES
from app.services.explainability_service import (
    shap_explain, lime_explain, gradcam_explain, heatmap_to_base64,
    compute_attention_weights,
)
from app.utils.file_handler             import save_upload, cleanup
from app.utils.response                 import success, error
from app.middleware.auth                import require_patient_or_doctor
from app.models                         import Patient, Prediction

logger    = logging.getLogger(__name__)
explain_bp = Blueprint("explain", __name__)

MODALITY_FEATURES = {
    "voice":    VOICE_FEATURES,
    "clinical": CLINICAL_FEATURES,
    "motor":    MOTOR_FEATURES,
}


# ── POST /explain/shap/<modality> ────────────────────────────
@explain_bp.post("/shap/<modality>")
@jwt_required()
@require_patient_or_doctor
def shap(modality):
    """
    Body: { "features": { "col": val, ... } }   (for tabular models)
    Returns SHAP feature importances.
    """
    if modality not in MODALITY_FEATURES:
        return error(f"SHAP explainability only supported for: {list(MODALITY_FEATURES.keys())}", 400)

    feature_names = MODALITY_FEATURES[modality]
    body          = request.get_json(silent=True) or {}
    feat_dict     = body.get("features", {})

    model  = ModelRegistry.get(modality)
    scaler = ModelRegistry.get(f"{modality}_scaler")
    if model is None:
        return error(f"{modality.title()} model not loaded", 503)

    X = np.array([[feat_dict.get(f, 0) for f in feature_names]])
    if scaler:
        X = scaler.transform(X)

    result = shap_explain(model, X, feature_names)
    return success(data=result)


# ── POST /explain/lime/<modality> ────────────────────────────
@explain_bp.post("/lime/<modality>")
@jwt_required()
@require_patient_or_doctor
def lime(modality):
    """LIME explanation for tabular models."""
    if modality not in MODALITY_FEATURES:
        return error(f"LIME only supported for: {list(MODALITY_FEATURES.keys())}", 400)

    feature_names = MODALITY_FEATURES[modality]
    body          = request.get_json(silent=True) or {}
    feat_dict     = body.get("features", {})

    model  = ModelRegistry.get(modality)
    scaler = ModelRegistry.get(f"{modality}_scaler")
    if model is None:
        return error(f"{modality.title()} model not loaded", 503)

    X = np.array([[feat_dict.get(f, 0) for f in feature_names]])
    if scaler:
        X = scaler.transform(X)

    result = lime_explain(model, X, feature_names)
    return success(data=result)


# ── POST /explain/gradcam ────────────────────────────────────
@explain_bp.post("/gradcam")
@jwt_required()
@require_patient_or_doctor
def gradcam():
    """
    Grad-CAM heatmap for MRI or Spiral CNN models.
    Form-data: image (file), model_type (mri|spiral)
    """
    if "image" not in request.files:
        return error("'image' file is required", 400)

    model_type = request.form.get("model_type", "mri")
    if model_type not in ("mri", "spiral"):
        return error("model_type must be 'mri' or 'spiral'", 400)

    model = ModelRegistry.get(model_type)
    if model is None:
        return error(f"{model_type.upper()} model not loaded", 503)

    try:
        img_path = save_upload(request.files["image"], "image")
        from PIL import Image
        img  = Image.open(img_path).convert("RGB")
        size = (224, 224) if model_type == "mri" else (128, 128)
        img  = img.resize(size)
        X    = np.expand_dims(np.array(img) / 255.0, 0).astype(np.float32)

        # Try common last conv layer names
        heatmap = None
        for layer_name in ("conv2d_last", "block5_conv3", "conv2d", "Conv_1"):
            try:
                heatmap = gradcam_explain(model, X, last_conv_layer_name=layer_name)
                if heatmap is not None:
                    break
            except Exception:
                continue

        heatmap_b64 = heatmap_to_base64(heatmap, size) if heatmap is not None else None

        return success(data={
            "model_type":          model_type,
            "heatmap_base64":      heatmap_b64,
            "heatmap_available":   heatmap_b64 is not None,
            "message":             "Grad-CAM heatmap generated" if heatmap_b64 else "Grad-CAM not available for this model architecture",
        })
    except Exception as exc:
        return error(f"Grad-CAM failed: {exc}", 500)
    finally:
        cleanup(img_path)


# ── GET /explain/fusion/<patient_id> ─────────────────────────
@explain_bp.get("/fusion/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def fusion_explanation(patient_id):
    """
    Full multi-modal explanation for a patient's latest fusion prediction.
    Aggregates SHAP for clinical + attention weights for fusion.
    """
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    # Latest fusion prediction
    latest_fusion = (Prediction.query
                     .filter_by(patient_id=patient.id, modality="fusion")
                     .order_by(Prediction.created_at.desc())
                     .first())

    attention = []
    modality_contributions = {}

    if latest_fusion and latest_fusion.raw_output:
        modality_contributions = latest_fusion.raw_output.get("modality_contributions", {})
        attention = list(compute_attention_weights(modality_contributions).values())

    # SHAP for clinical (if data available)
    latest_clinical = (Prediction.query
                       .filter_by(patient_id=patient.id, modality="clinical")
                       .order_by(Prediction.created_at.desc())
                       .first())

    clinical_shap = {}
    summary       = "No sufficient prediction data for full explainability."

    if latest_clinical and latest_clinical.raw_output:
        model  = ModelRegistry.get("clinical")
        scaler = ModelRegistry.get("clinical_scaler")
        if model:
            try:
                raw   = latest_clinical.raw_output
                X     = np.array([[raw.get("features", {}).get(f, 0) for f in CLINICAL_FEATURES]])
                if scaler:
                    X = scaler.transform(X)
                clinical_shap = shap_explain(model, X, CLINICAL_FEATURES)
                summary = clinical_shap.get("summary", "")
            except Exception as exc:
                logger.warning("Clinical SHAP failed in fusion explanation: %s", exc)

    return success(data={
        "features":              clinical_shap.get("top_features", []),
        "attention":             attention,
        "modality_contributions": modality_contributions,
        "summary":               summary,
        "mri_heatmap_url":       None,
        "spiral_heatmap_url":    None,
        "explanation_method":    "SHAP (clinical) + weighted attention (fusion)",
    })