"""
app/api/mri.py — Updated for PyTorch 4-CNN + PSO-ELM ensemble

Changes from original:
  - No longer requires a single 'mri' Keras model; checks for any CNN available
  - predict_mri() loads all 4 CNNs + PSO-ELM bundle from registry internally
  - Heatmap skipped (PyTorch Grad-CAM not implemented; edge overlay used instead)
  - All other logic (persist, report) unchanged
"""
import time
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.model_loader   import ModelRegistry
from app.services.image_service  import predict_mri
from app.utils.file_handler      import save_upload, cleanup
from app.utils.response          import error, prediction_response
from app.middleware.auth         import require_patient_or_doctor
from app.models                  import Prediction, Patient, Report
from app                         import db

logger = logging.getLogger(__name__)
mri_bp = Blueprint("mri", __name__)


@mri_bp.post("/predict")
@jwt_required()
@require_patient_or_doctor
def predict():
    if "mri_scan" not in request.files:
        return error("'mri_scan' image file is required", 400)

    patient_id = request.form.get("patient_id")

    # Require at least one MRI CNN to be loaded
    mri_available = any(
        ModelRegistry.is_available(k)
        for k in ("mri_effnet_b3", "mri_effnet_b4", "mri_resnet", "mri_densenet")
    )
    if not mri_available:
        return error("MRI CNN models not loaded on server", 503)

    try:
        img_path = save_upload(request.files["mri_scan"], "image")
    except ValueError as exc:
        return error(str(exc), 400)

    t0 = time.time()
    try:
        # predict_mri() loads all models from registry internally
        result = predict_mri(img_path)

        # ── Edge-detection visual (PyTorch Grad-CAM not implemented) ──
        heatmap_b64 = None
        try:
            heatmap_b64 = _generate_mri_visual(img_path)
        except Exception as hm_exc:
            logger.warning("MRI visual generation failed: %s", hm_exc)

        if heatmap_b64:
            result["heatmap_base64"] = heatmap_b64
            result["explainability"] = {
                "features": [
                    {"name": "MRI Ensemble Confidence",
                     "importance": round(result.get("confidence", 0), 4)},
                    {"name": "Parkinson Probability",
                     "importance": round(result.get("probability", 0), 4)},
                ],
                "summary": (
                    f"MRI 4-CNN + PSO-ELM ensemble: {result.get('label', '—')} "
                    f"(probability {round(result.get('probability', 0)*100, 1)}%, "
                    f"confidence {round(result.get('confidence', 0)*100, 1)}%)."
                ),
                "mri_heatmap_base64": heatmap_b64,
            }

    except ValueError as exc:
        cleanup(img_path)
        return error(str(exc), 422)
    except Exception as exc:
        cleanup(img_path)
        return error(f"MRI prediction error: {exc}", 500)
    finally:
        cleanup(img_path)

    elapsed = int((time.time() - t0) * 1000)

    if patient_id:
        identity = get_jwt_identity()
        user_id  = int(identity) if identity else None
        _persist(patient_id, "mri", result, user_id=user_id)

    logger.info("MRI prediction for %s: %s", patient_id, result.get("label"))
    return prediction_response("mri", result,
                               patient_id=patient_id, processing_ms=elapsed)


def _generate_mri_visual(img_path: str):
    """Grayscale + colour overlay for MRI visual feedback."""
    try:
        import cv2, numpy as np, base64
        img = cv2.imread(str(img_path))
        if img is None:
            return None
        resized  = cv2.resize(img, (224, 224))
        gray     = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        # Clahe-enhanced for MRI contrast
        clahe    = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        colored  = cv2.applyColorMap(enhanced, cv2.COLORMAP_HOT)
        rgb      = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        rgb_bgr  = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        overlay  = cv2.addWeighted(rgb_bgr, 0.5, colored, 0.5, 0)
        _, buf   = cv2.imencode(".png", overlay)
        return base64.b64encode(buf).decode("utf-8")
    except Exception as exc:
        logger.warning("MRI visual failed: %s", exc)
        return None


def _persist(patient_uid, modality, result, user_id=None):
    try:
        patient = Patient.query.filter_by(patient_uid=patient_uid).first()
        if not patient:
            return
        pred = Prediction(
            patient_id=patient.id, modality=modality,
            result=result.get("probability"), label=result.get("label"),
            severity=result.get("severity"), confidence=result.get("confidence"),
            raw_output=result,
        )
        db.session.add(pred)
        db.session.flush()
        conf = result.get("confidence")
        report = Report(
            patient_id=patient.id,
            title="MRI Scan Prediction Report",
            content={
                "prediction_id": pred.id, "modality": modality,
                "model_used": "MRI 4-CNN + PSO-ELM Ensemble (98.19%)",
                "result": result.get("label"),
                "severity": round(result.get("severity"), 1) if result.get("severity") is not None else None,
                "confidence": round(conf * 100, 1) if conf is not None else None,
                "probability": result.get("probability"),
                "has_parkinson": result.get("has_parkinson"),
                "individual_probs": result.get("individual_probs"),
                "notes": "Automated report from MRI 4-CNN + PSO-ELM ensemble analysis.",
            },
            created_by=user_id,
        )
        db.session.add(report)
        db.session.commit()
        logger.info("Persisted MRI prediction for %s", patient_uid)
    except Exception as exc:
        logger.error("MRI persist failed: %s", exc)
        db.session.rollback()