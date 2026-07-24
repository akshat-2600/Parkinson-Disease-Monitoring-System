"""
app/api/auth.py
Authentication endpoints — signup, login, refresh, logout, me.

IMPORTANT: Flask-JWT-Extended requires identity to be a STRING.
We store just the user ID as a string: str(user.id)
Role is stored in additional_claims.
"""
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt,
)
from app import db, bcrypt
from app.models import User, Patient, Doctor
from app.utils.response import success, error

auth_bp = Blueprint("auth", __name__)

# In-memory token blocklist (use Redis in production)
_blocklist: set = set()


def _make_tokens(user):
    """
    Identity = str(user.id) — must be a string for JWT spec.
    Role stored in additional_claims so middleware can skip DB lookups.
    """
    identity          = str(user.id)
    additional_claims = {"role": user.role}
    access_token  = create_access_token(identity=identity, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=identity, additional_claims=additional_claims)
    return access_token, refresh_token


# Signup
@auth_bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}

    for field in ("email", "password", "role"):
        if not data.get(field):
            return error(f"'{field}' is required", 400)

    role = data["role"].lower()
    if role not in ("doctor", "patient"):
        return error("role must be 'doctor' or 'patient'", 400)

    if User.query.filter_by(email=data["email"]).first():
        return error("Email already registered", 409)

    pw_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    user = User(
        email         = data["email"].lower().strip(),
        password_hash = pw_hash,
        role          = role,
        first_name    = data.get("first_name", ""),
        last_name     = data.get("last_name", ""),
        is_active     = True,
    )
    db.session.add(user)
    db.session.flush()

    if role == "patient":
        uid = data.get("patient_uid") or f"PT-{user.id:04d}"
        profile = Patient(
            user_id     = user.id,
            patient_uid = uid,
            age         = data.get("age"),
            gender      = data.get("gender"),
            diagnosis   = data.get("diagnosis", "Parkinson's Disease"),
            onset_year  = data.get("onset_year"),
        )
        db.session.add(profile)
    else:
        profile = Doctor(
            user_id        = user.id,
            specialisation = data.get("specialisation", "Neurology"),
            license_number = data.get("license_number", ""),
        )
        db.session.add(profile)

    db.session.commit()

    access_token, refresh_token = _make_tokens(user)

    extra = {}
    if role == "patient":
        extra["patient_uid"] = profile.patient_uid
    else:
        extra["doctor_id"] = profile.id

    return success(
        data={
            "user":          user.to_dict(),
            "access_token":  access_token,
            "refresh_token": refresh_token,
            **extra,
        },
        message="Account created successfully",
        status=201,
    )


# Login
@auth_bp.post("/login")
def login():
    data     = request.get_json(silent=True) or {}
    email    = data.get("email", "").lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return error("email and password are required", 400)

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return error("Invalid email or password", 401)

    if not user.is_active:
        return error("Account is deactivated", 403)

    access_token, refresh_token = _make_tokens(user)

    extra = {}
    if user.role == "patient" and user.patient_profile:
        extra["patient_uid"] = user.patient_profile.patient_uid
    elif user.role == "doctor" and user.doctor_profile:
        extra["doctor_id"] = user.doctor_profile.id

    return success(data={
        "user":          user.to_dict(),
        "access_token":  access_token,
        "refresh_token": refresh_token,
        **extra,
    })


# Refresh
@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    user     = User.query.get(int(identity))
    if not user:
        return error("User not found", 404)
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )
    return success(data={"access_token": access_token})


# Logout
@auth_bp.delete("/logout")
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    _blocklist.add(jti)
    return success(message="Logged out successfully")


# Me
@auth_bp.get("/me")
@jwt_required()
def me():
    identity = get_jwt_identity()
    user     = User.query.get(int(identity))
    if not user:
        return error("User not found", 404)

    profile = {}
    if user.role == "patient" and user.patient_profile:
        profile = user.patient_profile.to_dict()
    elif user.role == "doctor" and user.doctor_profile:
        profile = {
            "id":             user.doctor_profile.id,
            "specialisation": user.doctor_profile.specialisation,
            "license_number": user.doctor_profile.license_number,
        }

    return success(data={"user": user.to_dict(), "profile": profile})


# Change password
@auth_bp.put("/change-password")
@jwt_required()
def change_password():
    identity = get_jwt_identity()
    user     = User.query.get(int(identity))
    data     = request.get_json(silent=True) or {}

    if not bcrypt.check_password_hash(user.password_hash, data.get("current_password", "")):
        return error("Current password is incorrect", 401)

    new_pw = data.get("new_password", "")
    if len(new_pw) < 8:
        return error("New password must be at least 8 characters", 400)

    user.password_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
    db.session.commit()
    return success(message="Password updated successfully")