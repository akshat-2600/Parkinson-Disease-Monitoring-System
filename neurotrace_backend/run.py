"""
run.py — NeuroTrace application entry point.

Starting the app:
    python run.py                           # development (debug, auto-reload)
    gunicorn "run:app" --workers 4 --bind 0.0.0.0:5000   # production

What happens when you run this:
    1. Flask app is created via create_app()
    2. All API blueprints are mounted under /api/*
    3. All ML models are loaded into memory from ml_models/
    4. Flask starts serving:
         http://localhost:5000/          → index.html (the full UI)
         http://localhost:5000/api/...   → JSON API endpoints
    5. Open http://localhost:5000 in your browser — the app starts.

No separate frontend server needed. No CORS issues.
"""
import logging
from app import create_app
from app.services.model_loader import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("neurotrace")

# ── Create Flask app ──────────────────────────────────────────
app = create_app()

# ── Load ML models once at startup ───────────────────────────
with app.app_context():
    logger.info("Loading ML models…")
    ModelRegistry.load_all(app)
    status = ModelRegistry.status()
    loaded  = [k for k, v in status.items() if v]
    missing = [k for k, v in status.items() if not v]
    logger.info("Models loaded:  %s", loaded  or "none")
    if missing:
        logger.warning("Models missing: %s (predictions for these will be skipped)", missing)

# ── Start server ──────────────────────────────────────────────
if __name__ == "__main__":
    host  = "0.0.0.0"
    port  = 5000
    debug = app.config.get("DEBUG", True)

    logger.info("=" * 60)
    logger.info("  NeuroTrace — Parkinson's Intelligence Platform")
    logger.info("=" * 60)
    logger.info("  Open in browser:  http://127.0.0.1:%d", port)
    logger.info("  API base:         http://127.0.0.1:%d/api", port)
    logger.info("  Health check:     http://127.0.0.1:%d/health", port)
    logger.info("  Environment:      %s", "development" if debug else "production")
    logger.info("=" * 60)

    app.run(host=host, port=port, debug=debug)