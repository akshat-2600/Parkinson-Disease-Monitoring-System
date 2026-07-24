"""
app/services/model_loader.py

CRITICAL: custom_models is imported at the very top before ANY joblib.load()
call so ELM / PSO / PSO_ELM are registered in sys.modules['__main__'].
Without this, any pkl file containing those classes will raise:
  "Can't get attribute 'ELM' on <module '__main__'>"
"""

import os
import sys
import logging
import joblib

logger = logging.getLogger(__name__)

# ── Register ELM/PSO FIRST — before any pkl is loaded ────────────────────────
try:
    from app.ml_models.custom_models import ELM, PSO, PSO_ELM, _register_for_pickle
    _register_for_pickle()
    logger.info("ELM/PSO/PSO_ELM registered for pickle deserialization")
except Exception as _reg_err:
    logger.error("custom_models registration failed: %s", _reg_err)
    # Minimal stubs so the registry still boots
    import numpy as np

    class ELM:
        def __init__(self, *a, **kw): pass
        def predict_proba(self, X): return np.array([[0.5, 0.5]] * len(X))
        def predict(self, X): return np.zeros(len(X), dtype=int)
        def score(self, X, y): return 0.0
        def fit(self, X, y, W=None, b=None): return self

    class PSO:
        pass

    class PSO_ELM:
        pass

    # Still try to inject into __main__ as fallback
    _main = sys.modules.get("__main__")
    if _main:
        for _n, _c in [("ELM", ELM), ("PSO", PSO), ("PSO_ELM", PSO_ELM)]:
            if not hasattr(_main, _n):
                setattr(_main, _n, _c)


# ── PyTorch ───────────────────────────────────────────────────────────────────
try:
    import torch
    _TORCH_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _TORCH_OK     = True
    logger.info("PyTorch device: %s", _TORCH_DEVICE)
except ImportError:
    _TORCH_OK     = False
    _TORCH_DEVICE = None
    logger.warning("PyTorch not installed — CNN models disabled")

# ── timm ──────────────────────────────────────────────────────────────────────
try:
    import timm
    _TIMM_OK = True
except ImportError:
    _TIMM_OK = False
    logger.warning("timm not installed — EfficientNet will use torchvision fallback")


# ──────────────────────────────────────────────────────────────────────────────
# Generic loaders
# ──────────────────────────────────────────────────────────────────────────────

def _safe_exists(path):
    return bool(path and os.path.exists(path))


def _load_pkl(path: str):
    """
    Load a joblib/pickle file.
    ELM/PSO classes must be registered (done above) before this runs.
    """
    if not _safe_exists(path):
        logger.warning("Missing file: %s", path)
        return None
    try:
        obj = joblib.load(path)
        logger.info("Loaded pkl: %s", path)
        return obj
    except Exception as exc:
        logger.error("pkl load failed (%s): %s", path, exc)
        return None


def _load_keras(path: str):
    if not _safe_exists(path):
        return None
    try:
        import tensorflow as tf
        model = tf.keras.models.load_model(path)
        logger.info("Loaded Keras model: %s", path)
        return model
    except Exception as exc:
        logger.error("Keras load failed (%s): %s", path, exc)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# CNN architecture builders
# ──────────────────────────────────────────────────────────────────────────────

def _build_efficientnet_b3(num_classes: int = 2):
    import torch.nn as nn
    if _TIMM_OK:
        model = timm.create_model("efficientnet_b3", pretrained=False, num_classes=2)
        feat  = model.classifier.in_features
        model.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(feat, num_classes))
    else:
        from torchvision import models as tvm
        model = tvm.efficientnet_b3(weights=None)
        model.classifier[1] = nn.Linear(1536, num_classes)
    return model


def _build_efficientnet_b4(num_classes: int = 2):
    import torch.nn as nn
    if _TIMM_OK:
        model = timm.create_model("efficientnet_b4", pretrained=False, num_classes=2)
        feat  = model.classifier.in_features
        model.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(feat, num_classes))
    else:
        from torchvision import models as tvm
        model = tvm.efficientnet_b4(weights=None)
        model.classifier[1] = nn.Linear(1792, num_classes)
    return model


def _build_resnet50(num_classes: int = 2):
    import torch.nn as nn
    from torchvision import models as tvm
    model    = tvm.resnet50(weights=None)
    feat     = model.fc.in_features
    model.fc = nn.Sequential(nn.Dropout(0.3), nn.Linear(feat, num_classes))
    return model


def _build_densenet121(num_classes: int = 2):
    import torch.nn as nn
    from torchvision import models as tvm
    model = tvm.densenet121(weights=None)
    feat  = model.classifier.in_features  # 1024
    model.classifier = nn.Sequential(
        nn.BatchNorm1d(feat),
        nn.Dropout(0.4),
        nn.Linear(feat, 256),
        nn.ReLU(),
        nn.Dropout(0.3),
        nn.Linear(256, num_classes),
    )
    return model


def _load_torch_cnn(path: str, arch: str, num_classes: int = 2):
    """Build architecture then load state-dict from .pth checkpoint."""
    if not _TORCH_OK:
        return None
    if not _safe_exists(path):
        logger.warning("CNN checkpoint missing: %s", path)
        return None

    builders = {
        "efficientnet_b3": _build_efficientnet_b3,
        "efficientnet_b4": _build_efficientnet_b4,
        "resnet50":        _build_resnet50,
        "densenet121":     _build_densenet121,
    }
    builder = builders.get(arch)
    if builder is None:
        logger.error("Unknown CNN arch: %s", arch)
        return None

    try:
        model = builder(num_classes)
        state = torch.load(path, map_location="cpu")
        if isinstance(state, dict) and "model_state_dict" in state:
            state = state["model_state_dict"]
        model.load_state_dict(state, strict=False)
        model.to(_TORCH_DEVICE).eval()
        logger.info("Loaded %s: %s", arch, path)
        return model
    except Exception as exc:
        logger.error("CNN load failed (%s | %s): %s", arch, path, exc)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Model Registry
# ──────────────────────────────────────────────────────────────────────────────

class ModelRegistry:
    """
    Central store for every ML artefact used by NeuroTrace.

    Registry keys:
      spiral_effnet, spiral_resnet, spiral_bundle, spiral
      mri_effnet_b3, mri_effnet_b4, mri_resnet, mri_densenet, mri_bundle, mri
      voice, voice_scaler, voice_selected_features, voice_selector
      motor, motor_scaler, motor_imputer, motor_encoder, motor_feature_cols
      clinical, clinical_scaler, clinical_imputer, clinical_feature_cols
      fusion, fusion_meta_scaler
      timeseries
    """

    _models: dict = {}

    @classmethod
    def load_all(cls, app):
        cfg        = app.config
        cls._models = {}

        # ── Spiral ───────────────────────────────────────────
        cls._models["spiral_effnet"] = _load_torch_cnn(
            cfg.get("SPIRAL_EFFNET_PATH", ""), "efficientnet_b3"
        )
        cls._models["spiral_resnet"] = _load_torch_cnn(
            cfg.get("SPIRAL_RESNET_PATH", ""), "resnet50"
        )
        cls._models["spiral_bundle"] = _load_pkl(cfg.get("SPIRAL_BUNDLE_PATH", ""))
        cls._models["spiral"]        = cls._models["spiral_effnet"]  # backward-compat

        # ── MRI ──────────────────────────────────────────────
        cls._models["mri_effnet_b3"] = _load_torch_cnn(
            cfg.get("MRI_EFFNET_B3_PATH", ""), "efficientnet_b3"
        )
        cls._models["mri_effnet_b4"] = _load_torch_cnn(
            cfg.get("MRI_EFFNET_B4_PATH", ""), "efficientnet_b4"
        )
        cls._models["mri_resnet"] = _load_torch_cnn(
            cfg.get("MRI_RESNET_PATH", ""), "resnet50"
        )
        cls._models["mri_densenet"] = _load_torch_cnn(
            cfg.get("MRI_DENSENET_PATH", ""), "densenet121"
        )
        cls._models["mri_bundle"] = _load_pkl(cfg.get("MRI_BUNDLE_PATH", ""))
        cls._models["mri"] = (
            cls._models["mri_resnet"] or cls._models["mri_effnet_b3"]
        )

        # ── Voice ────────────────────────────────────────────
        voice_pkl = _load_pkl(cfg.get("VOICE_MODEL_PATH", ""))
        cls._models["voice"] = voice_pkl.get("model") if isinstance(voice_pkl, dict) and "model" in voice_pkl else voice_pkl
        cls._models["voice_scaler"]            = _load_pkl(cfg.get("VOICE_SCALER_PATH", ""))
        cls._models["voice_selected_features"] = _load_pkl(cfg.get("VOICE_SELECTED_FEATURES_PATH", ""))
        sel_path = cfg.get("VOICE_SELECTOR_PATH", "")
        cls._models["voice_selector"] = _load_pkl(sel_path) if _safe_exists(sel_path) else None

        # ── Motor ────────────────────────────────────────────
        cls._models["motor"]              = _load_pkl(cfg.get("MOTOR_MODEL_PATH", ""))
        cls._models["motor_scaler"]       = _load_pkl(cfg.get("MOTOR_SCALER_PATH", ""))
        cls._models["motor_imputer"]      = _load_pkl(cfg.get("MOTOR_IMPUTER_PATH", ""))
        cls._models["motor_encoder"]      = _load_pkl(cfg.get("MOTOR_ENCODER_PATH", ""))
        cls._models["motor_feature_cols"] = _load_pkl(cfg.get("MOTOR_FEATURE_COLS_PATH", ""))

        # ── Clinical ─────────────────────────────────────────
        cls._models["clinical"]              = _load_pkl(cfg.get("CLINICAL_MODEL_PATH", ""))
        cls._models["clinical_scaler"]       = _load_pkl(cfg.get("CLINICAL_SCALER_PATH", ""))
        cls._models["clinical_imputer"]      = _load_pkl(cfg.get("CLINICAL_IMPUTER_PATH", ""))
        cls._models["clinical_feature_cols"] = _load_pkl(cfg.get("CLINICAL_FEATURE_COLS_PATH", ""))

        # ── Fusion ───────────────────────────────────────────
        cls._models["fusion"]             = _load_pkl(cfg.get("FUSION_MODEL_PATH", ""))
        cls._models["fusion_meta_scaler"] = _load_pkl(cfg.get("FUSION_META_SCALER_PATH", ""))

        # ── Timeseries ───────────────────────────────────────
        ts_path = cfg.get("TIMESERIES_MODEL_PATH", "")
        if _safe_exists(ts_path):
            ext = os.path.splitext(ts_path)[1].lower()
            cls._models["timeseries"] = (
                _load_keras(ts_path) if ext in (".h5", ".keras") else _load_pkl(ts_path)
            )
        else:
            cls._models["timeseries"] = None

        # ── Summary ──────────────────────────────────────────
        loaded  = [k for k, v in cls._models.items() if v is not None]
        missing = [k for k, v in cls._models.items() if v is None]
        logger.info("Models loaded (%d): %s",  len(loaded),  loaded)
        if missing:
            logger.warning("Models missing (%d): %s", len(missing), missing)

    @classmethod
    def get(cls, name):
        return cls._models.get(name)

    @classmethod
    def is_available(cls, name):
        return cls._models.get(name) is not None

    @classmethod
    def status(cls):
        return {k: (v is not None) for k, v in cls._models.items()}

    @classmethod
    def available_models(cls):
        return [k for k, v in cls._models.items() if v is not None]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def predict_safe(fn, *args, **kwargs):
    """Wrap a prediction call; return None on any exception."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning(
            "predict_safe caught error in %s: %s",
            getattr(fn, "__name__", str(fn)), exc
        )
        return None


def get_torch_device():
    return _TORCH_DEVICE