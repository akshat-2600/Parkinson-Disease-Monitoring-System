"""
app/api/patients.py
Patient management endpoints.
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models          import Patient, Prediction, Report, User
from app.utils.response  import success, error
from app.middleware.auth import require_doctor, require_patient_or_doctor
from app                 import db

patients_bp = Blueprint("patients", __name__)


def _current_user():
    """Return User ORM object from JWT identity dict."""
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        user_id = identity.get("user_id")
    else:
        user_id = int(identity)
    return User.query.get(int(user_id)) if user_id else None


# ── List all patients (doctors only) ─────────────────────────
@patients_bp.get("/")
@jwt_required()
@require_doctor
def list_patients():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search   = request.args.get("search", "")

    query = Patient.query
    if search:
        query = query.filter(Patient.patient_uid.ilike(f"%{search}%"))

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    patients  = []

    for p in paginated.items:
        d = p.to_dict()
        if p.user:
            d["name"]  = f"{p.user.first_name} {p.user.last_name}".strip()
            d["email"] = p.user.email
        latest = (Prediction.query
                  .filter_by(patient_id=p.id, modality="fusion")
                  .order_by(Prediction.created_at.desc())
                  .first())
        d["latest_severity"] = latest.severity if latest else None
        patients.append(d)

    return success(data={
        "patients": patients,
        "total":    paginated.total,
        "pages":    paginated.pages,
        "page":     page,
        "per_page": per_page,
    })


# ── Get single patient profile ────────────────────────────────
@patients_bp.get("/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def get_patient(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    d = patient.to_dict()
    if patient.user:
        d["name"]  = f"{patient.user.first_name} {patient.user.last_name}".strip()
        d["email"] = patient.user.email

    total_preds = Prediction.query.filter_by(patient_id=patient.id).count()
    latest = (Prediction.query
              .filter_by(patient_id=patient.id, modality="fusion")
              .order_by(Prediction.created_at.desc())
              .first())
    d["total_predictions"] = total_preds
    d["latest_severity"]   = latest.severity if latest else None
    d["latest_prediction"] = latest.to_dict() if latest else None

    return success(data=d)


# ── Update patient profile ────────────────────────────────────
@patients_bp.put("/<patient_id>")
@jwt_required()
@require_patient_or_doctor
def update_patient(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    user = _current_user()
    if user and user.role == "patient" and patient.user_id != user.id:
        return error("You can only edit your own profile", 403)

    data = request.get_json(silent=True) or {}
    for field in ("age", "gender", "diagnosis", "onset_year", "notes"):
        if field in data:
            setattr(patient, field, data[field])

    db.session.commit()
    return success(data=patient.to_dict(), message="Profile updated")


# ── Prediction history ────────────────────────────────────────
@patients_bp.get("/<patient_id>/predictions")
@jwt_required()
@require_patient_or_doctor
def prediction_history(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    modality = request.args.get("modality")

    query = Prediction.query.filter_by(patient_id=patient.id)
    if modality:
        query = query.filter_by(modality=modality)

    paginated = query.order_by(Prediction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return success(data={
        "predictions": [p.to_dict() for p in paginated.items],
        "total":       paginated.total,
        "pages":       paginated.pages,
        "page":        page,
    })


# ── Reports ───────────────────────────────────────────────────
@patients_bp.get("/<patient_id>/reports")
@jwt_required()
@require_patient_or_doctor
def get_reports(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    reports = (Report.query
               .filter_by(patient_id=patient.id)
               .order_by(Report.created_at.desc())
               .all())

    return success(data={"reports": [r.to_dict() for r in reports]})


@patients_bp.post("/<patient_id>/reports")
@jwt_required()
@require_doctor
def create_report(patient_id):
    patient = Patient.query.filter_by(patient_uid=patient_id).first()
    if not patient:
        return error(f"Patient '{patient_id}' not found", 404)

    user = _current_user()
    data = request.get_json(silent=True) or {}

    report = Report(
        patient_id = patient.id,
        title      = data.get("title", "Clinical Report"),
        content    = data.get("content", {}),
        created_by = user.id if user else None,
    )
    db.session.add(report)
    db.session.commit()

    return success(data=report.to_dict(), message="Report created", status=201)



# """
# app/api/patients.py
# Patient management endpoints.

# GET  /patients/             — list all patients (doctors only)
# GET  /patients/<patient_id> — get patient profile
# PUT  /patients/<patient_id> — update patient profile (doctor or self)
# GET  /patients/<patient_id>/predictions — prediction history
# GET  /patients/<patient_id>/reports     — reports list
# """
# from flask import Blueprint, request
# from flask_jwt_extended import jwt_required, get_jwt_identity

# from app.models          import Patient, Prediction, Report, User
# from app.utils.response  import success, error
# from app.middleware.auth import require_doctor, require_patient_or_doctor
# from app                 import db

# patients_bp = Blueprint("patients", __name__)


# # ── List all patients (doctors only) ─────────────────────────
# @patients_bp.get("/")
# @jwt_required()
# @require_doctor
# def list_patients():
#     """GET /patients/ — paginated patient list."""
#     page     = request.args.get("page", 1, type=int)
#     per_page = request.args.get("per_page", 20, type=int)
#     search   = request.args.get("search", "")

#     query = Patient.query
#     if search:
#         query = query.filter(Patient.patient_uid.ilike(f"%{search}%"))

#     paginated = query.paginate(page=page, per_page=per_page, error_out=False)
#     patients  = []

#     for p in paginated.items:
#         d = p.to_dict()
#         if p.user:
#             d["name"]  = f"{p.user.first_name} {p.user.last_name}".strip()
#             d["email"] = p.user.email
#         # Latest severity
#         latest = (Prediction.query
#                   .filter_by(patient_id=p.id, modality="fusion")
#                   .order_by(Prediction.created_at.desc())
#                   .first())
#         d["latest_severity"] = latest.severity if latest else None
#         patients.append(d)

#     return success(data={
#         "patients":    patients,
#         "total":       paginated.total,
#         "pages":       paginated.pages,
#         "page":        page,
#         "per_page":    per_page,
#     })


# # ── Get single patient profile ────────────────────────────────
# @patients_bp.get("/<patient_id>")
# @jwt_required()
# @require_patient_or_doctor
# def get_patient(patient_id):
#     """GET /patients/<patient_id> — patient profile + summary stats."""
#     patient = Patient.query.filter_by(patient_uid=patient_id).first()
#     if not patient:
#         return error(f"Patient '{patient_id}' not found", 404)

#     d = patient.to_dict()
#     if patient.user:
#         d["name"]       = f"{patient.user.first_name} {patient.user.last_name}".strip()
#         d["email"]      = patient.user.email

#     # Summary stats
#     total_preds = Prediction.query.filter_by(patient_id=patient.id).count()
#     latest = (Prediction.query
#               .filter_by(patient_id=patient.id, modality="fusion")
#               .order_by(Prediction.created_at.desc())
#               .first())
#     d["total_predictions"] = total_preds
#     d["latest_severity"]   = latest.severity if latest else None
#     d["latest_prediction"] = latest.to_dict() if latest else None

#     return success(data=d)


# # ── Update patient profile ────────────────────────────────────
# @patients_bp.put("/<patient_id>")
# @jwt_required()
# @require_patient_or_doctor
# def update_patient(patient_id):
#     """PUT /patients/<patient_id> — update age, gender, notes etc."""
#     patient = Patient.query.filter_by(patient_uid=patient_id).first()
#     if not patient:
#         return error(f"Patient '{patient_id}' not found", 404)

#     # Enforce patient can only edit their own profile
#     identity = get_jwt_identity()
#     user     = User.query.get(int(identity))
#     if user.role == "patient" and patient.user_id != user.id:
#         return error("You can only edit your own profile", 403)

#     data = request.get_json(silent=True) or {}
#     for field in ("age", "gender", "diagnosis", "onset_year", "notes"):
#         if field in data:
#             setattr(patient, field, data[field])

#     db.session.commit()
#     return success(data=patient.to_dict(), message="Profile updated")


# # ── Prediction history ────────────────────────────────────────
# @patients_bp.get("/<patient_id>/predictions")
# @jwt_required()
# @require_patient_or_doctor
# def prediction_history(patient_id):
#     """GET /patients/<patient_id>/predictions?modality=&page=&per_page="""
#     patient = Patient.query.filter_by(patient_uid=patient_id).first()
#     if not patient:
#         return error(f"Patient '{patient_id}' not found", 404)

#     page     = request.args.get("page", 1, type=int)
#     per_page = request.args.get("per_page", 20, type=int)
#     modality = request.args.get("modality")

#     query = Prediction.query.filter_by(patient_id=patient.id)
#     if modality:
#         query = query.filter_by(modality=modality)

#     paginated = query.order_by(Prediction.created_at.desc()).paginate(
#         page=page, per_page=per_page, error_out=False
#     )

#     return success(data={
#         "predictions": [p.to_dict() for p in paginated.items],
#         "total":       paginated.total,
#         "pages":       paginated.pages,
#         "page":        page,
#     })


# # ── Reports ───────────────────────────────────────────────────
# @patients_bp.get("/<patient_id>/reports")
# @jwt_required()
# @require_patient_or_doctor
# def get_reports(patient_id):
#     """GET /patients/<patient_id>/reports"""
#     patient = Patient.query.filter_by(patient_uid=patient_id).first()
#     if not patient:
#         return error(f"Patient '{patient_id}' not found", 404)

#     reports = (Report.query
#                .filter_by(patient_id=patient.id)
#                .order_by(Report.created_at.desc())
#                .all())

#     return success(data={"reports": [r.to_dict() for r in reports]})


# @patients_bp.post("/<patient_id>/reports")
# @jwt_required()
# @require_doctor
# def create_report(patient_id):
#     """POST /patients/<patient_id>/reports — doctor creates a report."""
#     patient = Patient.query.filter_by(patient_uid=patient_id).first()
#     if not patient:
#         return error(f"Patient '{patient_id}' not found", 404)

#     identity = get_jwt_identity()
#     data     = request.get_json(silent=True) or {}

#     report = Report(
#         patient_id = patient.id,
#         title      = data.get("title", "Clinical Report"),
#         content    = data.get("content", {}),
#         created_by = int(identity),
#     )
#     db.session.add(report)
#     db.session.commit()

#     return success(data=report.to_dict(), message="Report created", status=201)