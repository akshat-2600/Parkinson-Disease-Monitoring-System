"""
app/utils/file_handler.py
Secure file upload utilities shared across all prediction endpoints.
"""
import os
import uuid
import logging
from pathlib import Path
from flask import current_app
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


def _allowed(filename: str, allowed_set: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


def save_upload(file_obj, category: str) -> str:
    """
    Save a werkzeug FileStorage object to UPLOAD_FOLDER/<category>/.
    Returns the absolute path to the saved file.
    Raises ValueError for disallowed extension or empty file.
    """
    if file_obj is None or file_obj.filename == "":
        raise ValueError("No file provided")

    ext = file_obj.filename.rsplit(".", 1)[-1].lower() if "." in file_obj.filename else ""

    # Determine allowed set from category
    cfg = current_app.config
    allowed_map = {
        "audio":   cfg["ALLOWED_AUDIO_EXT"],
        "image":   cfg["ALLOWED_IMAGE_EXT"],
        "data":    cfg["ALLOWED_DATA_EXT"],
    }
    allowed = allowed_map.get(category, cfg["ALLOWED_DATA_EXT"])

    if ext not in allowed:
        raise ValueError(f"File type '.{ext}' not allowed for category '{category}'. Allowed: {allowed}")

    dest_dir = Path(cfg["UPLOAD_FOLDER"]) / category
    dest_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}_{secure_filename(file_obj.filename)}"
    dest_path   = dest_dir / unique_name

    file_obj.save(str(dest_path))
    logger.info("Saved upload: %s", dest_path)
    return str(dest_path)


def cleanup(path: str):
    """Delete a file after prediction (optional — call explicitly if needed)."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("Could not delete temp file %s: %s", path, exc)