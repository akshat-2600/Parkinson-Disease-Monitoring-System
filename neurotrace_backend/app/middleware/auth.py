"""
app/middleware/auth.py
Role-based access control decorators.

JWT identity is always a plain string: str(user.id)
Set in app/api/auth.py via _make_tokens().
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt, verify_jwt_in_request
from app.models import User
import logging

logger = logging.getLogger(__name__)


def _get_user():
    """Return User from JWT identity string."""
    identity = get_jwt_identity()   # always str(user.id)
    if not identity:
        return None
    try:
        return User.query.get(int(identity))
    except (ValueError, TypeError):
        return None


def require_role(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = _get_user()
            if user is None or user.role not in roles:
                return jsonify({"error": "Access denied — insufficient permissions"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_doctor(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = _get_user()
        if user is None or user.role not in ("doctor", "admin"):
            return jsonify({"error": "Doctor access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def require_patient_or_doctor(fn):
    """
    Doctors/admins: unrestricted.
    Patients: can only access their own data (patient.user_id == user.id).
    Routes with no patient_id kwarg pass through for all authenticated users.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from app.models import Patient

        verify_jwt_in_request()
        user = _get_user()

        if user is None:
            return jsonify({"error": "User not found"}), 404

        if user.role in ("doctor", "admin"):
            return fn(*args, **kwargs)

        patient_uid = kwargs.get("patient_id") or kwargs.get("patient_uid")
        if not patient_uid:
            # No patient_id in URL (e.g. /realtime_predict) — allow through
            return fn(*args, **kwargs)

        patient = Patient.query.filter_by(patient_uid=patient_uid).first()
        if not patient:
            return jsonify({"error": f"Patient '{patient_uid}' not found"}), 404

        if patient.user_id != user.id:
            return jsonify({"error": "Access denied — you can only view your own data"}), 403

        return fn(*args, **kwargs)
    return wrapper


def get_current_user():
    try:
        return _get_user()
    except Exception:
        return None


# """
# app/middleware/auth.py
# Role-based access control decorators.

# Usage:
#     @jwt_required()
#     @require_role("doctor")
#     def doctor_only_endpoint():
#         ...
# """
# from functools import wraps
# from flask import jsonify
# from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

# from app.models import User


# def require_role(*roles):
#     """
#     Decorator: user must have one of the given roles.
#     Must be placed AFTER @jwt_required().
#     """
#     def decorator(fn):
#         @wraps(fn)
#         def wrapper(*args, **kwargs):
#             verify_jwt_in_request()
#             identity = get_jwt_identity()
#             user = User.query.get(int(identity))
#             if user is None or user.role not in roles:
#                 return jsonify({"error": "Access denied — insufficient permissions"}), 403
#             return fn(*args, **kwargs)
#         return wrapper
#     return decorator


# def require_doctor(fn):
#     """Shortcut: @require_doctor — only doctors allowed."""
#     @wraps(fn)
#     def wrapper(*args, **kwargs):
#         verify_jwt_in_request()
#         identity = get_jwt_identity()
#         user = User.query.get(int(identity))
#         if user is None or user.role not in ("doctor", "admin"):
#             return jsonify({"error": "Doctor access required"}), 403
#         return fn(*args, **kwargs)
#     return wrapper


# def require_patient_or_doctor(fn):
#     """
#     Patients can access only their own data.
#     Doctors can access any patient's data.
#     patient_id must be a keyword argument in the route.
#     """
#     @wraps(fn)
#     def wrapper(*args, **kwargs):
#         from app.models import Patient
#         from flask_jwt_extended import get_jwt
        
#         verify_jwt_in_request()
#         identity = get_jwt_identity()
#         user = User.query.get(int(identity))

#         if user is None:
#             return jsonify({"error": "User not found"}), 404

#         # Doctors and admins: unrestricted
#         if user.role in ("doctor", "admin"):
#             return fn(*args, **kwargs)

#         # Patients: check ownership via patient_uid
#         patient_uid = kwargs.get("patient_id") or kwargs.get("patient_uid")
#         if patient_uid:
#             # Prefer direct patient_id from JWT claims for self-access
#             claims = get_jwt()
#             if user.role == "patient" and claims.get("patient_uid") == patient_uid:
#                 return fn(*args, **kwargs)

#             patient = Patient.query.filter_by(patient_uid=patient_uid).first()
#             if not patient:
#                 return jsonify({"error": f"Patient '{patient_uid}' not found"}), 404

#             # Ensure assignment consistency
#             if patient.user_id != user.id:
#                 return jsonify({"error": "Access denied — you can only view your own data"}), 403
#             return fn(*args, **kwargs)

#         return fn(*args, **kwargs)
#     return wrapper


# def get_current_user():
#     """Helper: return the current User ORM object from JWT identity."""
#     identity = get_jwt_identity()
#     return User.query.get(int(identity)) if identity else None