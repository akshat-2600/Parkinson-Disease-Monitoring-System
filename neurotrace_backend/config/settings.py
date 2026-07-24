"""
config/settings.py
Centralised, environment-aware configuration.

All model paths default to ml_models/<Folder>/<file> and can be
overridden via environment variables or a .env file.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

_CONFIG_DIR   = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_CONFIG_DIR)


def _p(env_key: str, default_rel: str) -> str:
    """
    Return env override (if set) or default path resolved relative to backend root.
    Does NOT check whether the file exists — model_loader handles that.
    """
    env_val = os.getenv(env_key)
    if env_val:
        return env_val if os.path.isabs(env_val) else os.path.join(_BACKEND_ROOT, env_val)
    return os.path.join(_BACKEND_ROOT, default_rel)


class BaseConfig:
    # ── Core ─────────────────────────────────────────────────
    SECRET_KEY  = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FLASK_ENV   = os.getenv("FLASK_ENV", "development")

    # ── JWT ──────────────────────────────────────────────────
    JWT_SECRET_KEY            = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(
        seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", "2592000"))
    )
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME    = "Authorization"
    JWT_HEADER_TYPE    = "Bearer"

    # ── Database ─────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI        = os.getenv("DATABASE_URL", "sqlite:///neurotrace.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Uploads ──────────────────────────────────────────────
    UPLOAD_FOLDER      = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(50 * 1024 * 1024)))
    ALLOWED_AUDIO_EXT  = {"wav", "mp3", "mp4", "ogg", "flac", "m4a"}
    ALLOWED_IMAGE_EXT  = {"png", "jpg", "jpeg", "bmp", "tiff", "nii", "gz"}
    ALLOWED_DATA_EXT   = {"csv", "json", "xlsx"}

    # ── CORS ─────────────────────────────────────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # ──────────────────────────────────────────────────────────
    # SPIRAL  (EffNet-B3-FT2 TTA + ResNet50 + SVM ensemble)
    # ──────────────────────────────────────────────────────────
    SPIRAL_EFFNET_PATH = _p("SPIRAL_EFFNET_PATH", "app/ml_models/Spiral/best_efficientnet_b3_ft2.pth")
    SPIRAL_RESNET_PATH = _p("SPIRAL_RESNET_PATH", "app/ml_models/Spiral/best_resnet50.pth")
    SPIRAL_BUNDLE_PATH = _p("SPIRAL_BUNDLE_PATH", "app/ml_models/Spiral/best_ensemble_bundle.pkl")
    SPIRAL_MODEL_PATH  = _p("SPIRAL_MODEL_PATH",  "app/ml_models/Spiral/best_efficientnet_b3_ft2.pth")

    # ──────────────────────────────────────────────────────────
    # MRI  (4-CNN + PSO-ELM ensemble; 98.19%)
    # ──────────────────────────────────────────────────────────
    MRI_EFFNET_B3_PATH = _p("MRI_EFFNET_B3_PATH", "app/ml_models/MRI/best_efficientnet_b3.pth")
    MRI_EFFNET_B4_PATH = _p("MRI_EFFNET_B4_PATH", "app/ml_models/MRI/best_efficientnet_b4.pth")
    MRI_RESNET_PATH    = _p("MRI_RESNET_PATH",    "app/ml_models/MRI/best_resnet50.pth")
    MRI_DENSENET_PATH  = _p("MRI_DENSENET_PATH",  "app/ml_models/MRI/best_densenet121.pth")
    MRI_BUNDLE_PATH    = _p("MRI_BUNDLE_PATH",    "app/ml_models/MRI/final_bundle.pkl")
    MRI_MODEL_PATH     = _p("MRI_MODEL_PATH",     "app/ml_models/MRI/best_resnet50.pth")

    # ──────────────────────────────────────────────────────────
    # VOICE  (PSO-ELM; 92.31%)
    # ──────────────────────────────────────────────────────────
    VOICE_MODEL_PATH             = _p("VOICE_MODEL_PATH",             "app/ml_models/Voice/pso_elm_parkinsons_model.pkl")
    VOICE_SCALER_PATH            = _p("VOICE_SCALER_PATH",            "app/ml_models/Voice/scaler_voice.pkl")
    VOICE_SELECTED_FEATURES_PATH = _p("VOICE_SELECTED_FEATURES_PATH", "app/ml_models/Voice/selected_features.pkl")
    VOICE_SELECTOR_PATH          = _p("VOICE_SELECTOR_PATH",          "app/ml_models/Voice/voice_selector.pkl")

    # ──────────────────────────────────────────────────────────
    # MOTOR  (BEST_motor = Naive Bayes; 96.15%)
    # ──────────────────────────────────────────────────────────
    MOTOR_MODEL_PATH        = _p("MOTOR_MODEL_PATH",        "app/ml_models/Motor/BEST_motor.pkl")
    MOTOR_SCALER_PATH       = _p("MOTOR_SCALER_PATH",       "app/ml_models/Motor/scaler_motor.pkl")
    MOTOR_IMPUTER_PATH      = _p("MOTOR_IMPUTER_PATH",      "app/ml_models/Motor/imputer_motor.pkl")
    MOTOR_ENCODER_PATH      = _p("MOTOR_ENCODER_PATH",      "app/ml_models/Motor/label_encoder_motor.pkl")
    MOTOR_FEATURE_COLS_PATH = _p("MOTOR_FEATURE_COLS_PATH", "app/ml_models/Motor/motor_feature_cols.pkl")

    # ──────────────────────────────────────────────────────────
    # CLINICAL  (BEST_clinical = CatBoost; 95.96%)
    # ──────────────────────────────────────────────────────────
    CLINICAL_MODEL_PATH        = _p("CLINICAL_MODEL_PATH",        "app/ml_models/Clinical/BEST_clinical.pkl")
    CLINICAL_SCALER_PATH       = _p("CLINICAL_SCALER_PATH",       "app/ml_models/Clinical/scaler_clinical.pkl")
    CLINICAL_IMPUTER_PATH      = _p("CLINICAL_IMPUTER_PATH",      "app/ml_models/Clinical/imputer_clinical.pkl")
    CLINICAL_FEATURE_COLS_PATH = _p("CLINICAL_FEATURE_COLS_PATH", "app/ml_models/Clinical/clinical_feature_cols.pkl")

    # ──────────────────────────────────────────────────────────
    # FUSION  (LightGBM stacker; AUC 0.9456)
    # ──────────────────────────────────────────────────────────
    FUSION_MODEL_PATH       = _p("FUSION_MODEL_PATH",       "app/ml_models/Fusion/fusion_model.pkl")
    FUSION_META_SCALER_PATH = _p("FUSION_META_SCALER_PATH", "app/ml_models/Fusion/meta_scaler.pkl")
    FUSION_PIPELINE_PATH    = _p("FUSION_PIPELINE_PATH",    "app/ml_models/Fusion/fusion_complete_pipeline.pkl")

    # ──────────────────────────────────────────────────────────
    # TIMESERIES  (optional)
    # ──────────────────────────────────────────────────────────
    TIMESERIES_MODEL_PATH = _p("TIMESERIES_MODEL_PATH", "app/ml_models/timeseries_model.pkl")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG     = False
    FLASK_ENV = "production"


class TestingConfig(BaseConfig):
    TESTING                 = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return CONFIG_MAP.get(env, DevelopmentConfig)