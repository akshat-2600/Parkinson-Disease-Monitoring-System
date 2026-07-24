"""
app/models/db_models.py
SQLAlchemy ORM models for NeuroTrace.
"""
from datetime import datetime, timezone
from app import db


# ─────────────────────────────────────────────────────────────
# User / Auth
# ─────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default="patient")
    # role: "doctor" | "patient" | "admin"

    first_name    = db.Column(db.String(100))
    last_name     = db.Column(db.String(100))
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    patient_profile = db.relationship("Patient", back_populates="user", uselist=False)
    doctor_profile  = db.relationship("Doctor",  back_populates="user", uselist=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "email":      self.email,
            "role":       self.role,
            "first_name": self.first_name,
            "last_name":  self.last_name,
            "is_active":  self.is_active,
        }


class Doctor(db.Model):
    __tablename__ = "doctors"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    specialisation = db.Column(db.String(150))
    license_number = db.Column(db.String(50))

    user     = db.relationship("User",    back_populates="doctor_profile")
    patients = db.relationship("Patient", back_populates="doctor")


class Patient(db.Model):
    __tablename__ = "patients"

    id          = db.Column(db.Integer, primary_key=True)
    patient_uid = db.Column(db.String(20), unique=True, nullable=False)  # e.g. PT-001
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    doctor_id   = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)

    age         = db.Column(db.Integer)
    gender      = db.Column(db.String(10))
    ethnicity   = db.Column(db.String(50))
    diagnosis   = db.Column(db.String(150))
    onset_year  = db.Column(db.Integer)
    notes       = db.Column(db.Text)

    user        = db.relationship("User",    back_populates="patient_profile")
    doctor      = db.relationship("Doctor",  back_populates="patients")
    predictions = db.relationship("Prediction", back_populates="patient", cascade="all, delete-orphan")
    reports     = db.relationship("Report",     back_populates="patient", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":          self.id,
            "patient_uid": self.patient_uid,
            "age":         self.age,
            "gender":      self.gender,
            "diagnosis":   self.diagnosis,
            "onset_year":  self.onset_year,
            "doctor_id":   self.doctor_id,
        }


# ─────────────────────────────────────────────────────────────
# Predictions
# ─────────────────────────────────────────────────────────────
class Prediction(db.Model):
    __tablename__ = "predictions"

    id           = db.Column(db.Integer, primary_key=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    modality     = db.Column(db.String(30), nullable=False)
    # modality: voice | clinical | mri | spiral | motor | timeseries | fusion

    result       = db.Column(db.Float)          # probability / severity score
    label        = db.Column(db.String(50))     # e.g. "Parkinson's Detected"
    severity     = db.Column(db.Float)          # 0-100 normalised severity
    confidence   = db.Column(db.Float)          # model confidence
    raw_output   = db.Column(db.JSON)           # full model output dict
    input_meta   = db.Column(db.JSON)           # file names / feature counts
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    patient      = db.relationship("Patient", back_populates="predictions")

    def to_dict(self):
        return {
            "id":          self.id,
            "patient_id":  self.patient_id,
            "modality":    self.modality,
            "result":      self.result,
            "label":       self.label,
            "severity":    self.severity,
            "confidence":  self.confidence,
            "raw_output":  self.raw_output,
            "input_meta":  self.input_meta,
            "created_at":  self.created_at.isoformat(),
        }


class Report(db.Model):
    __tablename__ = "reports"

    id           = db.Column(db.Integer, primary_key=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    title        = db.Column(db.String(200))
    content      = db.Column(db.JSON)
    created_by   = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    patient      = db.relationship("Patient", back_populates="reports")

    def to_dict(self):
        return {
            "id":         self.id,
            "patient_id": self.patient_id,
            "title":      self.title,
            "content":    self.content,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }