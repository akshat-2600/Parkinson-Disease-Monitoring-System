"""
app/services/progression_service.py
─────────────────────────────────────────────────────────────
Module 3: Explainable Severity & Progression Modeling
Module 4: Patient-Specific Adaptation

Implements:
  1. Personalized baseline computation per patient
  2. Linear + polynomial regression forecasting on stored history
  3. LIME explanations for clinical and voice models
  4. Patient-specific severity trend classification
"""
import numpy as np
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 1. PATIENT-SPECIFIC BASELINE & ADAPTATION (Module 4)
# ─────────────────────────────────────────────────────────────

def compute_patient_baseline(predictions: list) -> dict:
    """
    Compute a personalized baseline for a patient from their prediction history.
    This is the patient-specific adaptation layer — each patient gets their own
    reference point rather than using a population-level threshold.

    predictions: list of Prediction ORM objects ordered by created_at asc
    """
    if not predictions:
        return {
            "baseline_severity":     None,
            "baseline_confidence":   None,
            "baseline_date":         None,
            "has_baseline":          False,
            "adaptation_status":     "no_data",
        }

    severities = [p.severity for p in predictions if p.severity is not None]
    if not severities:
        return {"has_baseline": False, "adaptation_status": "no_severity_data"}

    # Use the median of the first 3 predictions as the personal baseline
    # (avoids outlier skew from a single bad reading)
    early_preds  = severities[:min(3, len(severities))]
    baseline_sev = float(np.median(early_preds))
    latest_sev   = severities[-1]
    change       = latest_sev - baseline_sev
    pct_change   = (change / baseline_sev * 100) if baseline_sev > 0 else 0

    # Classify adaptation status relative to THIS patient's baseline
    if pct_change > 15:
        status = "significant_deterioration"
    elif pct_change > 5:
        status = "mild_deterioration"
    elif pct_change < -10:
        status = "improvement"
    else:
        status = "stable"

    return {
        "baseline_severity":   round(baseline_sev, 2),
        "baseline_date":       predictions[0].created_at.isoformat() if predictions else None,
        "latest_severity":     round(latest_sev, 2),
        "absolute_change":     round(change, 2),
        "percent_change":      round(pct_change, 1),
        "adaptation_status":   status,
        "has_baseline":        True,
        "n_predictions_used":  len(severities),
    }


# ─────────────────────────────────────────────────────────────
# 2. PROGRESSION FORECASTING (Module 3 + Objective 4)
# ─────────────────────────────────────────────────────────────

def forecast_progression(predictions: list, horizon_days: int = 90) -> dict:
    """
    Predict future severity progression using patient's own history.
    Uses both linear and polynomial regression; picks best fit by R².

    predictions: list of Prediction ORM objects (any modality with severity)
    horizon_days: how far ahead to forecast (default 90 days = 3 months)

    Returns forecast points and confidence intervals.
    """
    # Collect (days_since_first, severity) pairs
    data_points = []
    for p in predictions:
        if p.severity is None or p.created_at is None:
            continue
        data_points.append((p.created_at, p.severity))

    if len(data_points) < 2:
        return {
            "can_forecast":    False,
            "reason":          "Need at least 2 severity measurements to forecast",
            "min_required":    2,
            "current_count":   len(data_points),
        }

    data_points.sort(key=lambda x: x[0])
    t0 = data_points[0][0]

    def days_since(dt):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if t0.tzinfo is None:
            t0_aware = t0.replace(tzinfo=timezone.utc)
        else:
            t0_aware = t0
        return (dt - t0_aware).total_seconds() / 86400

    X = np.array([days_since(d[0]) for d in data_points])
    y = np.array([d[1] for d in data_points])

    # ── Fit linear model ─────────────────────────────────────
    lin_coeffs = np.polyfit(X, y, 1)
    lin_pred   = np.polyval(lin_coeffs, X)
    lin_r2     = _r2_score(y, lin_pred)

    # ── Fit polynomial (degree 2) if enough points ───────────
    poly_r2, poly_coeffs = lin_r2, lin_coeffs
    if len(data_points) >= 4:
        try:
            pc         = np.polyfit(X, y, 2)
            poly_pred  = np.polyval(pc, X)
            poly_r2    = _r2_score(y, poly_pred)
            if poly_r2 > lin_r2:
                poly_coeffs = pc
        except Exception:
            pass

    # Pick best model
    use_poly   = (poly_r2 > lin_r2 and len(data_points) >= 4)
    best_coeffs = poly_coeffs if use_poly else lin_coeffs
    best_r2     = poly_r2     if use_poly else lin_r2
    model_name  = "polynomial" if use_poly else "linear"

    # ── Residual std for confidence intervals ─────────────────
    fitted    = np.polyval(best_coeffs, X)
    residuals = y - fitted
    std_err   = float(np.std(residuals)) if len(residuals) > 1 else 5.0

    # ── Generate future forecast points ──────────────────────
    last_day  = float(X[-1])
    today     = datetime.now(timezone.utc)
    intervals = [7, 14, 30, 60, 90]  # days ahead

    forecast_points = []
    for d in intervals:
        if d > horizon_days:
            break
        future_day = last_day + d
        predicted  = float(np.clip(np.polyval(best_coeffs, future_day), 0, 100))
        ci_low     = float(np.clip(predicted - 1.96 * std_err, 0, 100))
        ci_high    = float(np.clip(predicted + 1.96 * std_err, 0, 100))
        future_dt  = today + timedelta(days=d)
        forecast_points.append({
            "days_ahead":     d,
            "date":           future_dt.strftime("%d %b %Y"),
            "predicted_sev":  round(predicted, 1),
            "ci_low":         round(ci_low, 1),
            "ci_high":        round(ci_high, 1),
            "stage":          _sev_to_stage(predicted),
        })

    # ── Trend classification ──────────────────────────────────
    slope = float(lin_coeffs[0])   # daily change
    if slope > 0.15:
        trend = "rapid_progression"
        trend_label = "Rapid Progression ⚠️"
    elif slope > 0.05:
        trend = "slow_progression"
        trend_label = "Slow Progression 📈"
    elif slope < -0.05:
        trend = "improving"
        trend_label = "Improving 📉"
    else:
        trend = "stable"
        trend_label = "Stable ✅"

    # ── Historical chart data (for overlay) ──────────────────
    hist_labels = []
    hist_values = []
    for i, (dt, sev) in enumerate(data_points):
        d = datetime(dt.year, dt.month, dt.day,
                     getattr(dt, 'hour', 0), getattr(dt, 'minute', 0))
        hist_labels.append(f"{d.day} {d.strftime('%b')}")
        hist_values.append(round(float(sev), 1))

    # Fitted curve over history
    fitted_curve = [round(float(np.clip(np.polyval(best_coeffs, x), 0, 100)), 1)
                    for x in X]

    return {
        "can_forecast":      True,
        "model":             model_name,
        "r_squared":         round(best_r2, 3),
        "daily_slope":       round(slope, 4),
        "trend":             trend,
        "trend_label":       trend_label,
        "forecast_points":   forecast_points,
        "std_error":         round(std_err, 2),
        # Chart overlay data
        "history_labels":    hist_labels,
        "history_values":    hist_values,
        "fitted_curve":      fitted_curve,
        "n_points":          len(data_points),
        "interpretation":    _interpret_forecast(slope, forecast_points, std_err),
    }


def _r2_score(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return float(1 - ss_res / (ss_tot + 1e-9))


def _sev_to_stage(s):
    if s < 20:  return "Stage 0"
    if s < 35:  return "Stage I"
    if s < 55:  return "Stage II"
    if s < 70:  return "Stage III"
    if s < 85:  return "Stage IV"
    return "Stage V"


def _interpret_forecast(slope, forecast_points, std_err):
    if not forecast_points:
        return "Insufficient data for interpretation."
    p90 = next((p for p in forecast_points if p["days_ahead"] == 90), None)
    if not p90:
        p90 = forecast_points[-1]
    sev = p90["predicted_sev"]
    days = p90["days_ahead"]
    monthly = slope * 30
    if slope > 0.1:
        return (f"The model predicts severity will reach {sev:.0f}/100 "
                f"in {days} days (~{monthly:.1f} points/month increase). "
                f"Clinical review recommended.")
    elif slope < -0.05:
        return (f"Severity shows a downward trend. Predicted {sev:.0f}/100 "
                f"in {days} days. Continue current treatment plan.")
    else:
        return (f"Severity is relatively stable. Predicted {sev:.0f}/100 "
                f"in {days} days (±{std_err:.1f} margin). Regular monitoring advised.")


# ─────────────────────────────────────────────────────────────
# 3. LIME EXPLANATIONS (Module 3)
# ─────────────────────────────────────────────────────────────

def lime_explain_clinical(model, scaler, raw_features: dict,
                          feature_names: list) -> dict:
    """
    LIME explanation for the clinical model.
    Returns top feature contributions with positive/negative direction.
    """
    try:
        from lime import lime_tabular
        import pandas as pd

        X_df = pd.DataFrame([{f: raw_features.get(f, 0) for f in feature_names}],
                            columns=feature_names)

        if scaler is not None:
            if hasattr(scaler, "feature_names_in_"):
                X_df = X_df.reindex(columns=list(scaler.feature_names_in_), fill_value=0.0)
            X_arr = scaler.transform(X_df)
            X_df  = pd.DataFrame(X_arr, columns=X_df.columns)

        if hasattr(model, "feature_names_in_"):
            X_df = X_df.reindex(columns=list(model.feature_names_in_), fill_value=0.0)

        feat_names = list(X_df.columns)
        X_np = X_df.values

        # Background data (zero vector as baseline)
        background = np.zeros((10, len(feat_names)))

        explainer = lime_tabular.LimeTabularExplainer(
            training_data         = background,
            feature_names         = feat_names,
            class_names           = ["No PD", "Parkinson's"],
            mode                  = "classification",
            discretize_continuous = True,
            random_state          = 42,
        )

        exp = explainer.explain_instance(
            X_np[0],
            model.predict_proba,
            num_features = min(10, len(feat_names)),
            num_samples  = 200,
        )

        lime_list = exp.as_list()
        features  = sorted(
            [{"name": item[0], "weight": round(float(item[1]), 4),
              "importance": abs(float(item[1])),
              "direction": "positive" if item[1] > 0 else "negative"}
             for item in lime_list],
            key=lambda x: x["importance"], reverse=True
        )

        pos = [f["name"] for f in features if f["direction"] == "positive"][:3]
        neg = [f["name"] for f in features if f["direction"] == "negative"][:3]
        parts = []
        if pos:
            parts.append(f"Features supporting Parkinson's diagnosis: {', '.join(pos)}")
        if neg:
            parts.append(f"Features arguing against diagnosis: {', '.join(neg)}")

        return {
            "method":   "lime",
            "features": features[:10],
            "summary":  ". ".join(parts) + "." if parts else "LIME analysis complete.",
            "success":  True,
        }

    except ImportError:
        logger.warning("LIME not installed")
        return {"success": False, "reason": "LIME library not installed"}
    except Exception as exc:
        logger.error("LIME clinical failed: %s", exc)
        return {"success": False, "reason": str(exc)}


def lime_explain_voice(model, scaler, raw_features: dict,
                       feature_names: list) -> dict:
    """LIME explanation for the voice model."""
    try:
        from lime import lime_tabular
        import pandas as pd

        X_df = pd.DataFrame([[raw_features.get(f, 0) for f in feature_names]],
                            columns=feature_names)

        if scaler is not None:
            if hasattr(scaler, "feature_names_in_"):
                X_df = X_df.reindex(columns=list(scaler.feature_names_in_), fill_value=0.0)
            X_arr = scaler.transform(X_df)
            X_df  = pd.DataFrame(X_arr, columns=X_df.columns)

        if hasattr(model, "feature_names_in_"):
            X_df = X_df.reindex(columns=list(model.feature_names_in_), fill_value=0.0)

        n_in = getattr(model, "n_features_in_", None)
        if n_in and X_df.shape[1] > n_in:
            X_df = X_df.iloc[:, :n_in]

        feat_names = list(X_df.columns)
        background = np.zeros((10, len(feat_names)))

        explainer = lime_tabular.LimeTabularExplainer(
            training_data         = background,
            feature_names         = feat_names,
            class_names           = ["No PD", "Parkinson's"],
            mode                  = "classification",
            discretize_continuous = True,
            random_state          = 42,
        )

        exp = explainer.explain_instance(
            X_df.values[0],
            model.predict_proba,
            num_features = min(10, len(feat_names)),
            num_samples  = 200,
        )

        features = sorted(
            [{"name": item[0], "weight": round(float(item[1]), 4),
              "importance": abs(float(item[1])),
              "direction": "positive" if item[1] > 0 else "negative"}
             for item in exp.as_list()],
            key=lambda x: x["importance"], reverse=True
        )

        pos = [f["name"] for f in features if f["direction"] == "positive"][:3]
        summary = f"Top voice biomarkers driving the prediction: {', '.join(pos)}." if pos else "LIME voice analysis complete."

        return {"method": "lime", "features": features[:10],
                "summary": summary, "success": True}

    except Exception as exc:
        logger.error("LIME voice failed: %s", exc)
        return {"success": False, "reason": str(exc)}