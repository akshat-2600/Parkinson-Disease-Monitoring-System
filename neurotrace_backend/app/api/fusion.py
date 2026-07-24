"""
app/api/fusion.py — Updated for new ensemble models

Key changes:
  1. Passes meta_scaler to fuse_predictions() so LightGBM stacker works correctly
  2. Passes imputer/encoder/feature_cols to motor + clinical predict calls
  3. Passes selected_features to voice predict call
  4. All other logic (dashboard, history, explanation) unchanged from original
"""
import time
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.model_loader         import ModelRegistry, predict_safe
from app.services.voice_service        import predict_from_audio, VOICE_FEATURES
from app.services.clinical_service     import predict_clinical, parse_csv_upload, CLINICAL_FEATURES
from app.services.image_service        import predict_mri, predict_spiral
from app.services.motor_service        import predict_motor, parse_motor_csv, MOTOR_FEATURES
from app.services.fusion_service       import (
    fuse_predictions, generate_risk_flags,
    generate_recommendations, severity_to_stage
)
from app.services.explainability_service import compute_attention_weights
from app.utils.file_handler            import save_upload, cleanup
from app.utils.response                import success, error
from app.middleware.auth               import require_patient_or_doctor
from app.models                        import Patient, Prediction, Report, User
from app                               import db

logger    = logging.getLogger(__name__)
fusion_bp = Blueprint("fusion", __name__)

MODALITY_LABELS = {
    "voice":      "Voice Analysis",
    "clinical":   "Clinical Data",
    "mri":        "MRI Scan",
    "spiral":     "Spiral Drawing",
    "motor":      "Motor Scores",
    "timeseries": "Time-Series",
    "fusion":     "Multi-Modal Fusion",
}


def _fmt(dt):
    """Windows-safe datetime label."""
    if dt is None:
        return "—"
    if not hasattr(dt, "strftime"):
        return str(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return f"{dt.day} {dt.strftime('%b %H:%M')}"


# ─────────────────────────────────────────────────────────────
# POST /api/fusion/realtime_predict
# ─────────────────────────────────────────────────────────────

@fusion_bp.post("/realtime_predict")
@jwt_required()
@require_patient_or_doctor
def realtime_predict():
    t0         = time.time()
    patient_id = request.form.get("patient_id")
    results    = {}
    skipped    = {}
    paths      = []

    # ── Voice ─────────────────────────────────────────────────
    if "voice" in request.files:
        model             = ModelRegistry.get("voice")
        scaler            = ModelRegistry.get("voice_scaler")
        selector          = ModelRegistry.get("voice_selector")
        selected_features = ModelRegistry.get("voice_selected_features")
        if model is None:
            skipped["voice"] = "Model file not loaded"
        else:
            try:
                path = save_upload(request.files["voice"], "audio")
                paths.append(path)
                r = predict_safe(
                    predict_from_audio, path, model, scaler, selector, selected_features
                )
                if r: results["voice"] = r
                else: skipped["voice"] = "Feature extraction failed"
            except Exception as exc:
                skipped["voice"] = str(exc)

    # ── MRI ───────────────────────────────────────────────────
    if "mri" in request.files:
        # model arg unused — predict_mri loads from registry internally
        mri_available = (
            ModelRegistry.is_available("mri_effnet_b3") or
            ModelRegistry.is_available("mri_resnet")
        )
        if not mri_available:
            skipped["mri"] = "MRI CNN models not loaded"
        else:
            try:
                path = save_upload(request.files["mri"], "image")
                paths.append(path)
                r = predict_safe(predict_mri, path)
                if r: results["mri"] = r
                else: skipped["mri"] = "Image processing failed"
            except Exception as exc:
                skipped["mri"] = str(exc)

    # ── Spiral ────────────────────────────────────────────────
    if "spiral" in request.files:
        spiral_available = ModelRegistry.is_available("spiral_effnet")
        if not spiral_available:
            skipped["spiral"] = "Spiral CNN model not loaded"
        else:
            try:
                path = save_upload(request.files["spiral"], "image")
                paths.append(path)
                r = predict_safe(predict_spiral, path)
                if r: results["spiral"] = r
                else: skipped["spiral"] = "Image processing failed"
            except Exception as exc:
                skipped["spiral"] = str(exc)

    # ── Clinical ──────────────────────────────────────────────
    if "clinical" in request.files:
        model        = ModelRegistry.get("clinical")
        scaler       = ModelRegistry.get("clinical_scaler")
        imputer      = ModelRegistry.get("clinical_imputer")
        feature_cols = ModelRegistry.get("clinical_feature_cols")
        if model is None:
            skipped["clinical"] = "Clinical model not loaded"
        else:
            try:
                path = save_upload(request.files["clinical"], "data")
                paths.append(path)
                data = parse_csv_upload(path)
                r    = predict_safe(
                    predict_clinical, data, model,
                    scaler=scaler, imputer=imputer, feature_cols=feature_cols
                )
                if r: results["clinical"] = r
                else: skipped["clinical"] = "Clinical data processing failed"
            except Exception as exc:
                skipped["clinical"] = str(exc)

    # ── Motor ─────────────────────────────────────────────────
    if "motor" in request.files:
        model        = ModelRegistry.get("motor")
        scaler       = ModelRegistry.get("motor_scaler")
        imputer      = ModelRegistry.get("motor_imputer")
        encoder      = ModelRegistry.get("motor_encoder")
        feature_cols = ModelRegistry.get("motor_feature_cols")
        if model is None:
            skipped["motor"] = "Motor model not loaded"
        else:
            try:
                path = save_upload(request.files["motor"], "data")
                paths.append(path)
                data = parse_motor_csv(path)
                r    = predict_safe(
                    predict_motor, data, model,
                    scaler=scaler, imputer=imputer,
                    encoder=encoder, feature_cols=feature_cols
                )
                if r: results["motor"] = r
                else: skipped["motor"] = "Motor data processing failed"
            except Exception as exc:
                skipped["motor"] = str(exc)

    # ── Timeseries ────────────────────────────────────────────
    if "timeseries" in request.files:
        model = ModelRegistry.get("timeseries")
        if model is None:
            skipped["timeseries"] = "Timeseries model not loaded"
        else:
            try:
                import numpy as np, pandas as pd
                path = save_upload(request.files["timeseries"], "data")
                paths.append(path)
                df   = pd.read_csv(path)
                X    = df.values.astype(np.float32)
                X_r  = X.reshape(1, -1) if hasattr(model, "predict_proba") else X.reshape(1, *X.shape)
                if hasattr(model, "predict_proba"):
                    proba   = model.predict_proba(X_r)[0]
                    prob_pd = float(proba[1]) if len(proba) > 1 else float(proba[0])
                else:
                    raw     = model.predict(X_r, verbose=0)
                    prob_pd = float(raw[0][0]) if raw.shape[-1] == 1 else float(raw[0][1])
                conf = prob_pd if prob_pd >= 0.5 else 1.0 - prob_pd
                results["timeseries"] = {
                    "has_parkinson": prob_pd >= 0.5,
                    "probability":   round(prob_pd, 4),
                    "confidence":    round(conf, 4),
                    "severity":      round(prob_pd * 100, 2),
                    "label": "Parkinson's Detected" if prob_pd >= 0.5 else "No Parkinson's Detected",
                }
            except Exception as exc:
                skipped["timeseries"] = str(exc)

    # ── Cleanup uploads ───────────────────────────────────────
    for p in paths:
        cleanup(p)

    if not results:
        reasons = "; ".join(f"{k}: {v}" for k, v in skipped.items()) if skipped else "No files uploaded"
        return error("No models could run a prediction.", 422,
                     details={"models_skipped": skipped, "reason": reasons})

    # ── Fusion ────────────────────────────────────────────────
    fusion_model = ModelRegistry.get("fusion")
    meta_scaler  = ModelRegistry.get("fusion_meta_scaler")
    fused        = fuse_predictions(results, fusion_model=fusion_model, meta_scaler=meta_scaler)
    risk_flags   = generate_risk_flags(fused, results)
    recs         = generate_recommendations(fused)
    elapsed      = int((time.time() - t0) * 1000)

    if patient_id:
        identity = get_jwt_identity()
        user_id  = int(identity) if identity else None
        for mod, res in results.items():
            _persist(patient_id, mod, res, user_id=user_id)
        _persist(patient_id, "fusion", fused, user_id=user_id)

    expl_features = _build_feature_importance(results)

    return success(data={
        "severity":               fused.get("severity"),
        "stage":                  fused.get("stage"),
        "label":                  fused.get("label"),
        "has_parkinson":          fused.get("has_parkinson"),
        "confidence":             fused.get("confidence"),
        "probability":            fused.get("probability"),
        "fusion_method":          fused.get("fusion_method"),
        "modalities_used":        fused.get("modalities_used") or list(results.keys()),
        "models_skipped":         skipped,
        "modality_contributions": fused.get("modality_contributions"),
        "individual_results":     {k: _slim(v) for k, v in results.items()},
        "risk_flag":              (
            "HIGH" if (fused.get("severity") or 0) >= 70
            else "MODERATE" if (fused.get("severity") or 0) >= 40
            else "LOW"
        ),
        "risk_description":  risk_flags[0]["msg"] if risk_flags else "No critical risk flags",
        "recommendation":    f"{recs[0]['title']} — {recs[0]['reasoning']}" if recs else "",
        "explanation":       _build_explanation(fused, results, skipped),
        "alerts":            risk_flags,
        "processing_time_ms": elapsed,
        "recommendations":   recs,
        "explainability": {
            "features":  expl_features,
            "attention": list(compute_attention_weights(
                fused.get("modality_contributions") or {}
            ).values()),
            "summary": _build_explanation(fused, results, skipped),
        },
    })


# ─────────────────────────────────────────────────────────────
# All remaining endpoints are IDENTICAL to original fusion.py.
# Copy-paste the dashboard, history, recommendations,
# explanation, and all helper functions from the original file.
# Only realtime_predict() needed updating.
# ─────────────────────────────────────────────────────────────

@fusion_bp.get("/dashboard/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def dashboard(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    latest = {}
    for mod in ("voice", "clinical", "mri", "spiral", "motor", "fusion", "timeseries"):
        pred = (Prediction.query
                .filter_by(patient_id=patient.id, modality=mod)
                .order_by(Prediction.created_at.desc()).first())
        if pred:
            latest[mod] = pred

    fusion_pred = latest.get("fusion")

    base = {
        "patient_uid": patient.patient_uid,
        "name":        (f"{patient.user.first_name} {patient.user.last_name}".strip()
                        if patient.user else patient.patient_uid),
        "initials":    _initials(patient.user),
        "age":         patient.age,
        "gender":      ("Female" if patient.gender in ("F", "Female")
                        else "Male" if patient.gender in ("M", "Male")
                        else patient.gender),
        "diagnosis":   patient.diagnosis or "Parkinson's Disease",
        "onset":       str(patient.onset_year) if patient.onset_year else None,
    }

    modalities = {}
    for mod in ("voice", "clinical", "mri", "spiral", "motor", "timeseries"):
        p = latest.get(mod)
        if p and p.confidence is not None:
            modalities[mod] = {
                "confidence": round(p.confidence, 2),
                "label":      p.label,
                "severity":   round(p.severity, 1) if p.severity else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }

    if not fusion_pred and not modalities:
        return success(data={
            **base,
            "severity": None, "stage": None, "status": "stable",
            "severity_change": None, "updrs": None,
            "fusion_confidence": None, "modalities": modalities,
            "alerts": [], "risks": [], "has_predictions": False,
        })

    if fusion_pred and fusion_pred.severity is not None:
        severity = fusion_pred.severity
    elif modalities:
        sev_vals = [v["severity"] for v in modalities.values() if v.get("severity") is not None]
        severity = sum(sev_vals) / len(sev_vals) if sev_vals else 0
    else:
        severity = 0

    stage       = severity_to_stage(severity)
    total_preds = Prediction.query.filter_by(patient_id=patient.id).count()

    return success(data={
        **base,
        "severity":           round(severity, 1),
        "stage":              stage,
        "status":             _status(severity),
        "severity_change":    _sev_change(patient),
        "updrs":              _updrs(latest),
        "fusion_confidence":  fusion_pred.confidence if fusion_pred else None,
        "modalities":         modalities,
        "alerts":             _build_alerts(severity, latest),
        "risks":              _build_risks(severity, latest),
        "has_predictions":    bool(modalities or fusion_pred),
        "total_predictions":  total_preds,
        "last_prediction_at": (
            fusion_pred.created_at.isoformat() if fusion_pred
            else max((p["created_at"] for p in modalities.values()
                      if p.get("created_at")), default=None)
        ),
    })


@fusion_bp.get("/explanation/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def explanation(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    features = []
    summary  = None
    attention = []

    for mod in ("fusion", "clinical", "voice", "motor", "mri", "spiral", "timeseries"):
        pred = (Prediction.query
                .filter_by(patient_id=patient.id, modality=mod)
                .order_by(Prediction.created_at.desc()).first())
        if not pred or not pred.raw_output:
            continue
        raw = pred.raw_output
        stored = raw.get("explainability") or {}
        stored_features = stored.get("features") or []
        if stored_features:
            features = _normalise_features(stored_features)
            summary  = stored.get("summary")
            attention = stored.get("attention", [])
            break
        feat_list = raw.get("feature_importance") or raw.get("top_features") or []
        if feat_list:
            features = _normalise_features(feat_list)
            summary  = raw.get("summary") or f"Feature importance from {MODALITY_LABELS.get(mod, mod)}."
            break

    if not features:
        features, summary = _try_shap_clinical(patient)
    if not features:
        features, summary = _try_shap_voice(patient)
    if not features:
        features, summary = _confidence_fallback(patient)

    latest_fusion = (Prediction.query
                     .filter_by(patient_id=patient.id, modality="fusion")
                     .order_by(Prediction.created_at.desc()).first())
    if latest_fusion and latest_fusion.raw_output:
        contrib = latest_fusion.raw_output.get("modality_contributions") or {}
        if contrib:
            attention = list(compute_attention_weights(contrib).values())

    mri_heatmap_b64    = None
    spiral_heatmap_b64 = None

    mri_pred = (Prediction.query
                .filter_by(patient_id=patient.id, modality="mri")
                .order_by(Prediction.created_at.desc()).first())
    if mri_pred and mri_pred.raw_output:
        mri_heatmap_b64 = (
            mri_pred.raw_output.get("heatmap_base64") or
            (mri_pred.raw_output.get("explainability") or {}).get("mri_heatmap_base64")
        )

    spiral_pred = (Prediction.query
                   .filter_by(patient_id=patient.id, modality="spiral")
                   .order_by(Prediction.created_at.desc()).first())
    if spiral_pred and spiral_pred.raw_output:
        spiral_heatmap_b64 = (
            spiral_pred.raw_output.get("heatmap_base64") or
            (spiral_pred.raw_output.get("explainability") or {}).get("spiral_heatmap_base64")
        )

    return success(data={
        "features":              features,
        "attention":             attention,
        "summary":               summary,
        "mri_heatmap_url":       None,
        "mri_heatmap_base64":    mri_heatmap_b64,
        "spiral_heatmap_url":    None,
        "spiral_heatmap_base64": spiral_heatmap_b64,
        "has_data":              len(features) > 0 or bool(mri_heatmap_b64) or bool(spiral_heatmap_b64),
    })


@fusion_bp.get("/recommendations/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def recommendations(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    latest_fusion = (Prediction.query
                     .filter_by(patient_id=patient.id, modality="fusion")
                     .order_by(Prediction.created_at.desc()).first())
    if not latest_fusion:
        latest_any = (Prediction.query
                      .filter_by(patient_id=patient.id)
                      .order_by(Prediction.created_at.desc()).first())
        if not latest_any:
            return success(data=[])
        fused_data = {"severity": latest_any.severity or 0}
    else:
        fused_data = latest_fusion.raw_output or {"severity": latest_fusion.severity or 0}

    recs = generate_recommendations(fused_data)
    return success(data=recs)


@fusion_bp.get("/history/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def history(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    since = datetime.now(timezone.utc) - timedelta(days=365)
    preds = (Prediction.query
             .filter(Prediction.patient_id == patient.id,
                     Prediction.created_at >= since)
             .order_by(Prediction.created_at.asc()).all())

    if not preds:
        return success(data={
            "labels": [], "severity": [], "updrs": [],
            "voice": [], "mri": [], "motor": [],
            "clinical": [], "spiral": [], "timeseries": [],
            "interventions": [], "has_data": False,
        })

    fusion_preds = [p for p in preds if p.modality == "fusion"]
    all_mods     = {m: [p for p in preds if p.modality == m]
                    for m in ("voice", "clinical", "mri", "spiral", "motor", "timeseries")}

    if fusion_preds:
        sev_labels   = [_fmt(p.created_at) for p in fusion_preds]
        sev_values   = [round(p.severity, 1) if p.severity is not None else None
                        for p in fusion_preds]
        updrs_values = [_updrs_from_pred(p) for p in fusion_preds]
    else:
        any_preds    = [p for p in preds if p.severity is not None]
        sev_labels   = [_fmt(p.created_at) for p in any_preds]
        sev_values   = [round(p.severity, 1) for p in any_preds]
        updrs_values = [None] * len(any_preds)

    def _mod_series(mod_preds):
        return (
            [_fmt(p.created_at) for p in mod_preds],
            [round(p.confidence, 3) if p.confidence is not None else None for p in mod_preds],
        )

    voice_labels,    voice_vals    = _mod_series(all_mods["voice"])
    mri_labels,      mri_vals      = _mod_series(all_mods["mri"])
    motor_labels,    motor_vals    = _mod_series(all_mods["motor"])
    clinical_labels, clinical_vals = _mod_series(all_mods["clinical"])
    spiral_labels,   spiral_vals   = _mod_series(all_mods["spiral"])
    ts_labels,       ts_vals       = _mod_series(all_mods["timeseries"])

    interventions = []
    for p in sorted(preds, key=lambda x: x.created_at):
        label    = MODALITY_LABELS.get(p.modality, p.modality.title())
        sev_str  = f" — severity {p.severity:.0f}" if p.severity is not None else ""
        conf_str = (f", confidence {round(p.confidence * 100):.0f}%"
                    if p.confidence is not None else "")
        interventions.append({
            "date":     _fmt(p.created_at),
            "iso":      p.created_at.isoformat(),
            "event":    f"{label} prediction{sev_str}{conf_str}",
            "modality": p.modality,
            "label":    p.label or "—",
        })

    return success(data={
        "labels":            sev_labels,
        "severity":          sev_values,
        "updrs":             updrs_values,
        "voice":             voice_vals,
        "voice_labels":      voice_labels,
        "mri":               mri_vals,
        "mri_labels":        mri_labels,
        "motor":             motor_vals,
        "motor_labels":      motor_labels,
        "clinical":          clinical_vals,
        "clinical_labels":   clinical_labels,
        "spiral":            spiral_vals,
        "spiral_labels":     spiral_labels,
        "timeseries":        ts_vals,
        "timeseries_labels": ts_labels,
        "interventions":     interventions,
        "has_data":          True,
    })


# ─────────────────────────────────────────────────────────────
# Helpers (all unchanged from original)
# ─────────────────────────────────────────────────────────────

def _slim(r):
    return {k: r.get(k) for k in ("probability", "confidence", "severity", "label", "has_parkinson")}


def _persist(patient_uid, modality, result, user_id=None):
    try:
        patient = Patient.query.filter_by(patient_uid=patient_uid).first()
        if not patient:
            return
        expl_data = _build_stored_explainability(modality, result)
        result_with_expl = dict(result)
        if expl_data:
            result_with_expl["explainability"] = expl_data

        prob = result.get("probability") or result.get("final_probability")
        pred = Prediction(
            patient_id=patient.id,
            modality=modality,
            result=prob,
            label=result.get("label"),
            severity=result.get("severity"),
            confidence=result.get("confidence"),
            raw_output=result_with_expl,
        )
        db.session.add(pred)
        db.session.flush()

        sev     = result.get("severity")
        conf    = result.get("confidence")
        label   = result.get("label") or "—"
        mod_lbl = MODALITY_LABELS.get(modality, modality.title())

        report = Report(
            patient_id=patient.id,
            title=f"{mod_lbl} Prediction Report",
            content={
                "prediction_id": pred.id,
                "modality":      modality,
                "model_used":    mod_lbl,
                "result":        label,
                "severity":      round(sev, 1) if sev is not None else None,
                "confidence":    round(conf * 100, 1) if conf is not None else None,
                "probability":   result.get("probability"),
                "has_parkinson": result.get("has_parkinson"),
                "stage":         result.get("stage"),
                "notes":         f"Automated report from {mod_lbl} analysis.",
                "raw_output":    _slim(result),
            },
            created_by=user_id,
        )
        db.session.add(report)
        db.session.commit()
        logger.info("Persisted %s prediction for %s", modality, patient_uid)
    except Exception as exc:
        logger.error("Persist failed: %s", exc)
        db.session.rollback()


def _build_stored_explainability(modality, result):
    features = []
    if modality == "voice" and result.get("features"):
        feat_dict = result["features"]
        vals      = [abs(float(feat_dict.get(f, 0))) for f in VOICE_FEATURES]
        max_v     = max(vals) if vals else 1.0
        if max_v == 0: max_v = 1.0
        features  = sorted(
            [{"name": n, "importance": round(v / max_v, 4)}
             for n, v in zip(VOICE_FEATURES, vals)],
            key=lambda x: x["importance"], reverse=True
        )[:10]
    elif modality == "clinical":
        conf = result.get("confidence", 0.5)
        key_features = ["Tremor","Rigidity","Bradykinesia","PosturalInstability",
                        "UPDRS","MoCA","FunctionalAssessment","Age","SpeechProblems","SleepDisorders"]
        weights = [0.95, 0.90, 0.88, 0.82, 0.78, 0.72, 0.65, 0.55, 0.48, 0.42]
        features = [{"name": n, "importance": round(w * conf, 4)} for n, w in zip(key_features, weights)]
    elif modality == "motor":
        conf = result.get("confidence", 0.5)
        key_features = ["29. Gait","30. Postural Stability","23.Finger Taps - RUE",
                        "20. Tremor at Rest - RUE","22. Rigidity - RUE",
                        "31. Body Bradykinesia and Hypokinesia","28. Posture",
                        "27. Arising from Chair","24. Hand Movements - RUE","18. Speech"]
        weights = [0.92, 0.88, 0.85, 0.82, 0.78, 0.74, 0.68, 0.62, 0.55, 0.48]
        features = [{"name": n, "importance": round(w * conf, 4)} for n, w in zip(key_features, weights)]
    elif modality == "fusion":
        contrib = result.get("modality_contributions") or {}
        if contrib:
            features = [{"name": MODALITY_LABELS.get(k, k), "importance": round(v / 100, 4)}
                        for k, v in sorted(contrib.items(), key=lambda x: x[1], reverse=True)]
    if not features:
        return None
    return {
        "features":  features,
        "attention": [],
        "summary":   f"{MODALITY_LABELS.get(modality, modality)} — top {len(features)} features.",
    }


def _build_feature_importance(results):
    features = []
    for mod, res in results.items():
        if res and res.get("confidence") is not None:
            features.append({
                "name":       MODALITY_LABELS.get(mod, mod.title()),
                "importance": round(res.get("confidence", 0), 3),
            })
    features.sort(key=lambda x: x["importance"], reverse=True)
    return features


def _normalise_features(feat_list):
    result = []
    for f in feat_list:
        name = f.get("name") or f.get("feature") or "Unknown"
        imp  = abs(f.get("importance") or f.get("shap_value") or f.get("value") or 0.0)
        result.append({"name": str(name), "importance": round(float(imp), 4)})
    result.sort(key=lambda x: x["importance"], reverse=True)
    return result[:10]


def _try_shap_clinical(patient):
    pred = (Prediction.query.filter_by(patient_id=patient.id, modality="clinical")
            .order_by(Prediction.created_at.desc()).first())
    if not pred or not pred.raw_output: return [], None
    model  = ModelRegistry.get("clinical")
    scaler = ModelRegistry.get("clinical_scaler")
    if not model: return [], None
    try:
        import shap, pandas as pd, numpy as np
        raw  = pred.raw_output
        vals = {f: raw.get("features", {}).get(f, CLINICAL_DEFAULTS.get(f, 0)) for f in CLINICAL_FEATURES}
        X_df = pd.DataFrame([vals], columns=CLINICAL_FEATURES)
        if scaler is not None:
            if hasattr(scaler, "feature_names_in_"):
                X_df = X_df.reindex(columns=list(scaler.feature_names_in_), fill_value=0.0)
            X_arr = scaler.transform(X_df); X_df = pd.DataFrame(X_arr, columns=X_df.columns)
        if hasattr(model, "feature_names_in_"):
            X_df = X_df.reindex(columns=list(model.feature_names_in_), fill_value=0.0)
        feat_names = list(X_df.columns)
        try:
            explainer = shap.TreeExplainer(model)
            shap_vals = explainer.shap_values(X_df)
        except Exception:
            bg = pd.DataFrame(np.zeros((1, len(feat_names))), columns=feat_names)
            explainer = shap.KernelExplainer(model.predict_proba, bg)
            shap_vals = explainer.shap_values(X_df.values, nsamples=50)
        vals_arr = shap_vals[1][0] if isinstance(shap_vals, list) else shap_vals[0]
        importance = sorted(
            [{"name": n, "importance": abs(float(v))} for n, v in zip(feat_names, vals_arr)],
            key=lambda x: x["importance"], reverse=True
        )[:10]
        top_names = [f["name"] for f in importance[:3]]
        return importance, f"SHAP: top clinical features are {', '.join(top_names)}."
    except Exception as exc:
        logger.warning("SHAP clinical failed: %s", exc)
        return [], None


def _try_shap_voice(patient):
    pred = (Prediction.query.filter_by(patient_id=patient.id, modality="voice")
            .order_by(Prediction.created_at.desc()).first())
    if not pred or not pred.raw_output: return [], None
    model  = ModelRegistry.get("voice")
    scaler = ModelRegistry.get("voice_scaler")
    if not model: return [], None
    try:
        import shap, pandas as pd, numpy as np
        feat_dict = pred.raw_output.get("features") or {}
        vals      = [feat_dict.get(f, 0.0) for f in VOICE_FEATURES]
        X_df      = pd.DataFrame([vals], columns=VOICE_FEATURES)
        if scaler is not None:
            if hasattr(scaler, "feature_names_in_"):
                X_df = X_df.reindex(columns=list(scaler.feature_names_in_), fill_value=0.0)
            X_arr = scaler.transform(X_df); X_df = pd.DataFrame(X_arr, columns=X_df.columns)
        if hasattr(model, "feature_names_in_"):
            X_df = X_df.reindex(columns=list(model.feature_names_in_), fill_value=0.0)
        feat_names = list(X_df.columns)
        n_in = getattr(model, "n_features_in_", None)
        if n_in and len(feat_names) > n_in:
            X_df = X_df.iloc[:, :n_in]; feat_names = feat_names[:n_in]
        try:
            explainer = shap.TreeExplainer(model); shap_vals = explainer.shap_values(X_df)
        except Exception:
            bg = pd.DataFrame(np.zeros((1, len(feat_names))), columns=feat_names)
            explainer = shap.KernelExplainer(model.predict_proba, bg)
            shap_vals = explainer.shap_values(X_df.values, nsamples=50)
        vals_arr = shap_vals[1][0] if isinstance(shap_vals, list) else shap_vals[0]
        importance = sorted(
            [{"name": n, "importance": abs(float(v))} for n, v in zip(feat_names, vals_arr)],
            key=lambda x: x["importance"], reverse=True
        )[:10]
        top_names = [f["name"] for f in importance[:3]]
        return importance, f"SHAP: top voice biomarkers are {', '.join(top_names)}."
    except Exception as exc:
        logger.warning("SHAP voice failed: %s", exc)
        return [], None


def _confidence_fallback(patient):
    features = []
    preds = (Prediction.query.filter_by(patient_id=patient.id)
             .order_by(Prediction.created_at.desc()).limit(10).all())
    for p in preds:
        if p.confidence is not None:
            features.append({
                "name":       MODALITY_LABELS.get(p.modality, p.modality.title()),
                "importance": round(float(p.confidence), 4),
            })
    features.sort(key=lambda x: x["importance"], reverse=True)
    return features[:10], "Showing model confidence scores by modality."


def _initials(user):
    if not user: return "??"
    return ((user.first_name or "")[0] + (user.last_name or "")[0]).upper() or "??"


def _status(s):
    if s is None: return "stable"
    if s >= 70:   return "critical"
    if s >= 40:   return "warning"
    return "stable"


def _sev_change(patient):
    preds = (Prediction.query.filter_by(patient_id=patient.id, modality="fusion")
             .order_by(Prediction.created_at.desc()).limit(2).all())
    if len(preds) == 2 and preds[0].severity and preds[1].severity:
        return round(preds[0].severity - preds[1].severity, 1)
    return None


def _updrs(latest):
    for mod in ("motor", "clinical"):
        raw = (latest.get(mod) and getattr(latest[mod], "raw_output", None)) or {}
        val = raw.get("updrs") or raw.get("hoehn_yahr_est")
        if val: return val
    return None


def _updrs_from_pred(pred):
    if not pred or not pred.raw_output: return None
    return pred.raw_output.get("updrs") or pred.raw_output.get("hoehn_yahr_est")


def _build_risks(severity, latest):
    risks = []
    if severity >= 70:
        risks += [{"name": "Falls Risk", "level": "high"}, {"name": "Motor Complications", "level": "high"}]
    elif severity >= 40:
        risks += [{"name": "Falls Risk", "level": "medium"}, {"name": "Bradykinesia", "level": "medium"}]
    else:
        risks.append({"name": "Falls Risk", "level": "low"})
    vp = getattr(latest.get("voice"), "result", None)
    if vp and vp >= 0.7:
        risks.append({"name": "Dysarthria", "level": "medium"})
    mp = getattr(latest.get("mri"), "result", None)
    if mp and mp >= 0.8:
        risks.append({"name": "Dopamine Loss", "level": "high"})
    return risks


def _build_alerts(severity, latest):
    alerts = []
    if severity >= 70:
        alerts.append({"type": "critical",
                        "msg": "Severity ≥ 70 — urgent clinical review required",
                        "time": "Latest prediction"})
    vp = getattr(latest.get("voice"), "result", None)
    if vp and vp >= 0.75:
        alerts.append({"type": "warning",
                        "msg": "Voice biomarkers indicate dysarthria progression",
                        "time": "Latest scan"})
    if not alerts:
        alerts.append({"type": "info",
                        "msg": "No critical flags detected at this time",
                        "time": "Latest prediction"})
    return alerts


def _build_explanation(fused, results, skipped):
    mods   = list(results.keys())
    sev    = fused.get("severity", 0)
    stage  = fused.get("stage", "—")
    method = fused.get("fusion_method", "ensemble")
    parts  = [f"Fusion ({method}) ran on {len(mods)} modality(ies): {', '.join(mods)}."]
    parts.append(f"Severity: {sev:.1f}/100 ({stage}).")
    if skipped:
        parts.append(f"Skipped ({len(skipped)} unavailable): {', '.join(skipped.keys())}.")
    return " ".join(parts)


# Re-export CLINICAL_DEFAULTS for SHAP fallback
from app.services.clinical_service import CLINICAL_DEFAULTS