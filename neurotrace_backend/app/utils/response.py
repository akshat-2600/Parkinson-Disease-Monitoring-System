"""
app/utils/response.py
Standardised JSON response builders for all API endpoints.
"""
from flask import jsonify
from datetime import datetime, timezone


def success(data=None, message="Success", status=200, **kwargs):
    payload = {
        "status":    "success",
        "message":   message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload), status


def error(message="An error occurred", status=400, details=None):
    payload = {
        "status":    "error",
        "message":   message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details:
        payload["details"] = details
    return jsonify(payload), status


def prediction_response(modality: str, result: dict, patient_id: str = None,
                         processing_ms: int = None):
    """Wrap a model result dict in a standardised prediction envelope."""
    payload = {
        "status":    "success",
        "modality":  modality,
        "result":    result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if patient_id:
        payload["patient_id"] = patient_id
    if processing_ms is not None:
        payload["processing_time_ms"] = processing_ms
    return jsonify(payload), 200