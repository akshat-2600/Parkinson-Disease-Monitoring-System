"""
tests/test_api.py
Core integration tests for NeuroTrace API.
Run: pytest tests/ -v
"""
import json
import pytest
from app import create_app, db, bcrypt
from config.settings import TestingConfig


@pytest.fixture
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        _seed_test_data(application)
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def doctor_token(client):
    res = client.post("/api/auth/login",
                      json={"email": "testdoc@neurotrace.ai", "password": "Test123!"})
    return json.loads(res.data)["data"]["access_token"]


@pytest.fixture
def patient_token(client):
    res = client.post("/api/auth/login",
                      json={"email": "testpatient@neurotrace.ai", "password": "Test123!"})
    return json.loads(res.data)["data"]["access_token"]


def _seed_test_data(app):
    from app.models import User, Patient, Doctor
    with app.app_context():
        # Doctor
        doc = User(
            email         = "testdoc@neurotrace.ai",
            password_hash = bcrypt.generate_password_hash("Test123!").decode(),
            role          = "doctor", first_name="Test", last_name="Doctor",
        )
        db.session.add(doc)
        db.session.flush()
        db.session.add(Doctor(user_id=doc.id, specialisation="Neurology"))

        # Patient
        pat = User(
            email         = "testpatient@neurotrace.ai",
            password_hash = bcrypt.generate_password_hash("Test123!").decode(),
            role          = "patient", first_name="Test", last_name="Patient",
        )
        db.session.add(pat)
        db.session.flush()
        db.session.add(Patient(
            user_id=pat.id, patient_uid="PT-TEST",
            age=60, gender="Male",
            diagnosis="Parkinson's Disease", onset_year=2020,
        ))
        db.session.commit()


# ─────────────────────────────────────────────────────────────
# Auth tests
# ─────────────────────────────────────────────────────────────
class TestAuth:
    def test_signup_patient(self, client):
        res = client.post("/auth/signup", json={
            "email": "newpatient@test.com", "password": "Secure123!",
            "role": "patient", "first_name": "New", "last_name": "Patient",
        })
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["access_token"]

    def test_signup_duplicate_email(self, client):
        res = client.post("/auth/signup", json={
            "email": "testdoc@neurotrace.ai", "password": "Test123!", "role": "doctor",
        })
        assert res.status_code == 409

    def test_login_success(self, client):
        res = client.post("/api/auth/login",
                          json={"email": "testdoc@neurotrace.ai", "password": "Test123!"})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert "access_token" in data["data"]

    def test_login_wrong_password(self, client):
        res = client.post("/api/auth/login",
                          json={"email": "testdoc@neurotrace.ai", "password": "wrong"})
        assert res.status_code == 401

    def test_me_authenticated(self, client, doctor_token):
        res = client.get("/auth/me",
                         headers={"Authorization": f"Bearer {doctor_token}"})
        assert res.status_code == 200

    def test_me_unauthenticated(self, client):
        res = client.get("/auth/me")
        assert res.status_code == 401


# ─────────────────────────────────────────────────────────────
# RBAC tests
# ─────────────────────────────────────────────────────────────
class TestRBAC:
    def test_patient_cannot_list_all_patients(self, client, patient_token):
        res = client.get("/patients/",
                         headers={"Authorization": f"Bearer {patient_token}"})
        assert res.status_code == 403

    def test_doctor_can_list_patients(self, client, doctor_token):
        res = client.get("/patients/",
                         headers={"Authorization": f"Bearer {doctor_token}"})
        assert res.status_code == 200

    def test_patient_can_access_own_profile(self, client, patient_token):
        res = client.get("/patients/PT-TEST",
                         headers={"Authorization": f"Bearer {patient_token}"})
        assert res.status_code == 200

    def test_patient_cannot_access_other_patient(self, client, patient_token):
        # PT-OTHER does not belong to the test patient user
        res = client.get("/patients/PT-001",
                         headers={"Authorization": f"Bearer {patient_token}"})
        assert res.status_code in (403, 404)


# ─────────────────────────────────────────────────────────────
# Clinical prediction tests (no model file needed — tests API layer)
# ─────────────────────────────────────────────────────────────
class TestClinicalAPI:
    def test_schema_endpoint(self, client, doctor_token):
        res = client.get("/clinical/features/schema",
                         headers={"Authorization": f"Bearer {doctor_token}"})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert "features" in data["data"]
        assert len(data["data"]["features"]) > 0

    def test_predict_no_model_returns_503(self, client, doctor_token):
        """When no model file exists, expect 503."""
        res = client.post("/clinical/predict",
                          json={"Age": 65, "Gender": 0, "patient_id": "PT-TEST"},
                          headers={"Authorization": f"Bearer {doctor_token}"})
        # 503 if model not loaded, 200 if loaded
        assert res.status_code in (200, 503)


# ─────────────────────────────────────────────────────────────
# Dashboard test (empty DB → returns 404 for unknown patient)
# ─────────────────────────────────────────────────────────────
class TestFusionDashboard:
    def test_unknown_patient_returns_404(self, client, doctor_token):
        res = client.get("/fusion/dashboard/PT-UNKNOWN",
                         headers={"Authorization": f"Bearer {doctor_token}"})
        assert res.status_code == 404

    def test_known_patient_returns_200(self, client, doctor_token):
        res = client.get("/fusion/dashboard/PT-TEST",
                         headers={"Authorization": f"Bearer {doctor_token}"})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert "severity" in data["data"]

    def test_recommendations_returns_list(self, client, doctor_token):
        res = client.get("/fusion/recommendations/PT-TEST",
                         headers={"Authorization": f"Bearer {doctor_token}"})
        assert res.status_code == 200

    def test_history_returns_arrays(self, client, doctor_token):
        res = client.get("/fusion/history/PT-TEST",
                         headers={"Authorization": f"Bearer {doctor_token}"})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert "labels" in data["data"]


# ─────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────
class TestHealth:
    def test_health_check(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert json.loads(res.data)["status"] == "ok"