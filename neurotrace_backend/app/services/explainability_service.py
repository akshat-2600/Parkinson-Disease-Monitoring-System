"""
app/services/explainability_service.py
SHAP + LIME explainability for each modality model.
"""
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# SHAP explainability
# ─────────────────────────────────────────────────────────────
def shap_explain(model, X: np.ndarray, feature_names: list,
                 background_data: Optional[np.ndarray] = None) -> dict:
    """
    Compute SHAP values for a single sample X.
    Returns feature importances and a per-sample explanation.
    """
    try:
        import shap

        if background_data is None:
            background_data = np.zeros((1, X.shape[1]))

        # Tree-based models → TreeExplainer (fastest)
        try:
            explainer = shap.TreeExplainer(model)
            shap_vals = explainer.shap_values(X)
        except Exception:
            # Fallback: KernelExplainer (model-agnostic, slower)
            explainer = shap.KernelExplainer(
                model.predict_proba, background_data
            )
            shap_vals = explainer.shap_values(X, nsamples=100)

        # For binary classification, use positive class (index 1)
        if isinstance(shap_vals, list):
            vals = shap_vals[1][0]
        else:
            vals = shap_vals[0]

        importance = [
            {"feature": name, "shap_value": float(v), "importance": abs(float(v))}
            for name, v in zip(feature_names, vals)
        ]
        importance.sort(key=lambda x: x["importance"], reverse=True)

        return {
            "method":              "shap",
            "feature_importance":  importance,
            "top_features":        importance[:10],
            "base_value":          float(explainer.expected_value[1]) if isinstance(explainer.expected_value, list) else float(explainer.expected_value),
            "summary":             _shap_summary(importance[:5]),
        }

    except ImportError:
        logger.warning("SHAP not installed — returning placeholder explanation")
        return _placeholder_explanation(feature_names)
    except Exception as exc:
        logger.error("SHAP explanation failed: %s", exc)
        return _placeholder_explanation(feature_names)


# ─────────────────────────────────────────────────────────────
# LIME explainability
# ─────────────────────────────────────────────────────────────
def lime_explain(model, X: np.ndarray, feature_names: list,
                 num_features: int = 10, num_samples: int = 500) -> dict:
    """
    LIME explanation for a tabular model prediction.
    """
    try:
        from lime import lime_tabular
        import numpy as np

        explainer = lime_tabular.LimeTabularExplainer(
            training_data   = np.zeros((10, X.shape[1])),
            feature_names   = feature_names,
            class_names     = ["No PD", "PD"],
            mode            = "classification",
            discretize_continuous = True,
        )

        exp = explainer.explain_instance(
            X[0],
            model.predict_proba,
            num_features=num_features,
            num_samples=num_samples,
        )

        lime_list = exp.as_list()
        importance = [
            {"feature": item[0], "weight": float(item[1]), "importance": abs(float(item[1]))}
            for item in lime_list
        ]
        importance.sort(key=lambda x: x["importance"], reverse=True)

        return {
            "method":             "lime",
            "feature_importance": importance,
            "top_features":       importance[:num_features],
            "summary":            _lime_summary(importance[:5]),
        }

    except ImportError:
        logger.warning("LIME not installed — returning placeholder")
        return _placeholder_explanation(feature_names, method="lime")
    except Exception as exc:
        logger.error("LIME explanation failed: %s", exc)
        return _placeholder_explanation(feature_names, method="lime")


# ─────────────────────────────────────────────────────────────
# CNN attention map (Grad-CAM) for image models
# ─────────────────────────────────────────────────────────────
def gradcam_explain(model, image_array: np.ndarray,
                    last_conv_layer_name: str = "conv2d") -> Optional[np.ndarray]:
    """
    Grad-CAM heatmap for a Keras CNN model.
    Returns a 2D numpy heatmap (H, W) or None on failure.
    """
    try:
        import tensorflow as tf

        grad_model = tf.keras.models.Model(
            inputs  = model.inputs,
            outputs = [model.get_layer(last_conv_layer_name).output, model.output],
        )

        with tf.GradientTape() as tape:
            conv_out, predictions = grad_model(image_array, training=False)
            # Use the predicted class
            class_idx = tf.argmax(predictions[0])
            loss = predictions[:, class_idx]

        grads     = tape.gradient(loss, conv_out)
        pool_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        conv_out   = conv_out[0]
        heatmap    = conv_out @ pool_grads[..., tf.newaxis]
        heatmap    = tf.squeeze(heatmap)
        heatmap    = tf.maximum(heatmap, 0) / (tf.math.reduce_max(heatmap) + 1e-8)
        return heatmap.numpy()

    except Exception as exc:
        logger.error("Grad-CAM failed: %s", exc)
        return None


def heatmap_to_base64(heatmap: np.ndarray, original_size: tuple = (224, 224)) -> Optional[str]:
    """Convert a Grad-CAM heatmap to a base64 PNG string."""
    try:
        import cv2
        import base64

        hm_uint8 = np.uint8(255 * heatmap)
        hm_color = cv2.applyColorMap(
            cv2.resize(hm_uint8, original_size), cv2.COLORMAP_JET
        )
        _, buf = cv2.imencode(".png", hm_color)
        return base64.b64encode(buf).decode("utf-8")
    except Exception as exc:
        logger.error("Heatmap conversion failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────
# Attention weights (for fusion model explainability)
# ─────────────────────────────────────────────────────────────
def compute_attention_weights(modality_contributions: dict) -> dict:
    """Convert modality contribution % to 0-1 attention weights."""
    total = sum(modality_contributions.values()) or 1
    return {k: round(v / total, 4) for k, v in modality_contributions.items()}


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _shap_summary(top_features: list) -> str:
    if not top_features:
        return "No SHAP explanation available."
    top = [f["feature"] for f in top_features]
    return (
        f"The model's decision was most influenced by: "
        f"{', '.join(top[:3])}. "
        f"These features collectively drove the Parkinson's classification."
    )


def _lime_summary(top_features: list) -> str:
    if not top_features:
        return "No LIME explanation available."
    pos = [f["feature"] for f in top_features if f["weight"] > 0]
    neg = [f["feature"] for f in top_features if f["weight"] < 0]
    parts = []
    if pos:
        parts.append(f"Features supporting PD diagnosis: {', '.join(pos[:3])}")
    if neg:
        parts.append(f"Features opposing PD diagnosis: {', '.join(neg[:3])}")
    return ". ".join(parts) + "."


def _placeholder_explanation(feature_names: list, method: str = "shap") -> dict:
    """Return a mock explanation when library is unavailable."""
    rng = np.random.default_rng(42)
    vals = rng.uniform(0, 1, len(feature_names))
    vals /= vals.sum()
    importance = sorted(
        [{"feature": n, "shap_value": float(v), "importance": float(v)}
         for n, v in zip(feature_names, vals)],
        key=lambda x: x["importance"], reverse=True
    )
    return {
        "method":             method,
        "feature_importance": importance,
        "top_features":       importance[:10],
        "summary":            f"[Placeholder] Top features: {', '.join(f['feature'] for f in importance[:3])}",
        "note":               "Install shap/lime for real explanations.",
    }