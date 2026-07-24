"""
NeuroTrace API Test Suite
Run from your project root:
    python test_all_endpoints.py

What it tests:
    - Auth (signup, login, refresh, me, logout)
    - Fusion (dashboard, history, explanation, recommendations)
    - Patients (list, get, predictions, reports)
    - Progression (baseline, forecast, lime, summary)
    - Health check

Output: colored PASS/FAIL for every endpoint
"""
import requests
import json
import sys
import os

BASE = "http://127.0.0.1:5000/api"

# ── Terminal colors ───────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = 0
failed = 0
access_token  = None
refresh_token = None
patient_uid   = None


def ok(label, detail=""):
    global passed
    passed += 1
    print(f"  {GREEN}✅ PASS{RESET}  {label}" + (f"  →  {CYAN}{detail}{RESET}" if detail else ""))


def fail(label, reason=""):
    global failed
    failed += 1
    print(f"  {RED}❌ FAIL{RESET}  {label}" + (f"  →  {RED}{reason}{RESET}" if reason else ""))


def section(name):
    print(f"\n{BOLD}{CYAN}{'─'*55}{RESET}")
    print(f"{BOLD}{CYAN}  {name}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*55}{RESET}")


def check(label, resp, expected_status=200, key=None):
    """Generic check: assert status code and optionally a key in response."""
    try:
        if resp.status_code != expected_status:
            fail(label, f"HTTP {resp.status_code} (expected {expected_status}): {resp.text[:120]}")
            return None
        j = resp.json()
        if key and key not in j.get("data", {}):
            fail(label, f"Missing key '{key}' in response data")
            return None
        detail = ""
        if "data" in j:
            d = j["data"]
            if isinstance(d, dict):
                # Show a couple of useful values
                for k in ("severity", "label", "probability", "confidence",
                          "access_token", "patient_uid", "role", "trend_label",
                          "can_forecast", "has_baseline", "adaptation_status"):
                    if k in d:
                        v = d[k]
                        detail = f"{k}={str(v)[:40]}"
                        break
        ok(label, detail)
        return j
    except Exception as e:
        fail(label, str(e))
        return None


# ─────────────────────────────────────────────────────────────
# 0. HEALTH CHECK
# ─────────────────────────────────────────────────────────────
section("0. Health Check")
try:
    r = requests.get("http://127.0.0.1:5000/health", timeout=5)
    if r.status_code == 200:
        ok("GET /health", r.json().get("service"))
    else:
        fail("GET /health", f"HTTP {r.status_code}")
except Exception as e:
    fail("GET /health", f"Server not reachable: {e}")
    print(f"\n{RED}  ⚠ Server is not running. Start it with: python run.py{RESET}\n")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# 1. AUTH ENDPOINTS
# ─────────────────────────────────────────────────────────────
section("1. Authentication")

# 1a. Signup (new patient)
r = requests.post(f"{BASE}/auth/signup", json={
    "email":      "testpatient_check@neurotrace.ai",
    "password":   "TestPass123!",
    "role":       "patient",
    "first_name": "Test",
    "last_name":  "Patient",
})
j = check("POST /auth/signup", r, 201, "access_token")
if j:
    access_token  = j["data"]["access_token"]
    refresh_token = j["data"]["refresh_token"]
    patient_uid   = j["data"].get("patient_uid")

# 1b. Login
r = requests.post(f"{BASE}/auth/login", json={
    "email":    "testpatient_check@neurotrace.ai",
    "password": "TestPass123!",
})
j = check("POST /auth/login", r, 200, "access_token")
if j:
    access_token  = j["data"]["access_token"]
    refresh_token = j["data"]["refresh_token"]
    if not patient_uid:
        patient_uid = j["data"].get("patient_uid")

# 1c. Wrong password
r = requests.post(f"{BASE}/auth/login", json={
    "email": "testpatient_check@neurotrace.ai", "password": "WRONG"})
if r.status_code == 401:
    ok("POST /auth/login (wrong password) → 401")
else:
    fail("POST /auth/login (wrong password)", f"Expected 401, got {r.status_code}")

# 1d. Get /me
HEADERS = {"Authorization": f"Bearer {access_token}"} if access_token else {}
r = requests.get(f"{BASE}/auth/me", headers=HEADERS)
check("GET /auth/me", r, 200, "user")

# 1e. Refresh
r = requests.post(f"{BASE}/auth/refresh",
                  headers={"Authorization": f"Bearer {refresh_token}"})
j = check("POST /auth/refresh", r, 200, "access_token")
if j:
    access_token = j["data"]["access_token"]
    HEADERS = {"Authorization": f"Bearer {access_token}"}

# 1f. Change password
r = requests.put(f"{BASE}/auth/change-password", headers=HEADERS, json={
    "current_password": "TestPass123!",
    "new_password":     "TestPass456!",
})
check("PUT /auth/change-password", r, 200)
# Change it back
requests.post(f"{BASE}/auth/login", json={
    "email": "testpatient_check@neurotrace.ai", "password": "TestPass456!"})


# ─────────────────────────────────────────────────────────────
# 2. DOCTOR LOGIN (needed for patient listing)
# ─────────────────────────────────────────────────────────────
section("2. Doctor Auth")
r = requests.post(f"{BASE}/auth/login", json={
    "email": "doctor@neurotrace.ai", "password": "Doctor123!"})
j = check("POST /auth/login (doctor)", r, 200, "access_token")
DOC_HEADERS = {}
if j:
    doc_token  = j["data"]["access_token"]
    DOC_HEADERS = {"Authorization": f"Bearer {doc_token}"}


# ─────────────────────────────────────────────────────────────
# 3. PATIENT ENDPOINTS
# ─────────────────────────────────────────────────────────────
section("3. Patient Management")

# Use doctor token for listing patients
r = requests.get(f"{BASE}/patients/?page=1&per_page=10", headers=DOC_HEADERS)
j = check("GET /patients/ (doctor)", r, 200, "patients")
pid = "PT-001"   # seeded patient
if j and j["data"].get("patients"):
    pid = j["data"]["patients"][0].get("patient_uid", "PT-001")

r = requests.get(f"{BASE}/patients/{pid}", headers=DOC_HEADERS)
check(f"GET /patients/{pid}", r, 200)

r = requests.get(f"{BASE}/patients/{pid}/predictions", headers=DOC_HEADERS)
check(f"GET /patients/{pid}/predictions", r, 200)

r = requests.get(f"{BASE}/patients/{pid}/reports", headers=DOC_HEADERS)
check(f"GET /patients/{pid}/reports", r, 200)

# Patient can only access their own data
if patient_uid:
    r = requests.get(f"{BASE}/patients/{patient_uid}", headers=HEADERS)
    check(f"GET /patients/{patient_uid} (self)", r, 200)

    r = requests.get(f"{BASE}/patients/{pid}", headers=HEADERS)
    if r.status_code == 403:
        ok(f"GET /patients/{pid} (other patient) → 403 correctly denied")
    else:
        fail(f"Access control check", f"Expected 403, got {r.status_code}")


# ─────────────────────────────────────────────────────────────
# 4. FUSION / DASHBOARD ENDPOINTS
# ─────────────────────────────────────────────────────────────
section("4. Fusion & Dashboard")

r = requests.get(f"{BASE}/fusion/dashboard/{pid}", headers=DOC_HEADERS)
check(f"GET /fusion/dashboard/{pid}", r, 200)

r = requests.get(f"{BASE}/fusion/history/{pid}", headers=DOC_HEADERS)
check(f"GET /fusion/history/{pid}", r, 200)

r = requests.get(f"{BASE}/fusion/explanation/{pid}", headers=DOC_HEADERS)
check(f"GET /fusion/explanation/{pid}", r, 200)

r = requests.get(f"{BASE}/fusion/recommendations/{pid}", headers=DOC_HEADERS)
check(f"GET /fusion/recommendations/{pid}", r, 200)

# 404 for non-existent patient
r = requests.get(f"{BASE}/fusion/dashboard/PT-XXXX", headers=DOC_HEADERS)
if r.status_code == 404:
    ok("GET /fusion/dashboard/PT-XXXX → 404 correctly")
else:
    fail("404 check", f"Expected 404, got {r.status_code}")


# ─────────────────────────────────────────────────────────────
# 5. PREDICTION ENDPOINTS (file uploads)
# ─────────────────────────────────────────────────────────────
section("5. Prediction Endpoints (file upload)")

# Create a minimal test CSV for clinical
import tempfile, csv
clinical_row = {
    "Age":67,"Gender":1,"Ethnicity":0,"EducationLevel":2,"BMI":26.5,
    "Smoking":0,"AlcoholConsumption":1,"PhysicalActivity":3,
    "DietQuality":6,"SleepQuality":7,
    "FamilyHistoryParkinsons":1,"TraumaticBrainInjury":0,
    "Hypertension":1,"Diabetes":0,"Depression":0,"Stroke":0,
    "SystolicBP":130,"DiastolicBP":82,
    "CholesterolTotal":195,"CholesterolLDL":120,"CholesterolHDL":55,
    "CholesterolTriglycerides":145,
    "UPDRS":35,"MoCA":24,"FunctionalAssessment":2.5,
    "Tremor":1,"Rigidity":1,"Bradykinesia":1,"PosturalInstability":0,
    "SpeechProblems":0,"SleepDisorders":1,"Constipation":0,
}
tf_clinical = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="")
writer = csv.DictWriter(tf_clinical, fieldnames=list(clinical_row.keys()))
writer.writeheader(); writer.writerow(clinical_row)
tf_clinical.close()

r = requests.post(f"{BASE}/clinical/predict",
    headers=DOC_HEADERS,
    data={"patient_id": pid},
    files={"clinical_data": ("clinical_test.csv", open(tf_clinical.name, "rb"), "text/csv")})
check("POST /clinical/predict", r, 200)
os.unlink(tf_clinical.name)

# Motor CSV test
motor_row = {
    "Age (years)":68,"Gender":1,
    "Positive history of Parkinson disease in family":1,
    "Age of disease onset (years)":62,
    "Duration of disease from first symptoms (years)":6,
    "Antidepressant therapy":0,"Antiparkinsonian medication":1,
    "Antipsychotic medication":0,"Benzodiazepine medication":0,
    "Levodopa equivalent (mg/day)":400,"Clonazepam (mg/day)":0,
    "18. Speech":1,"19. Facial Expression":1,
    "20. Tremor at Rest - head":0,"20. Tremor at Rest - RUE":2,
    "20. Tremor at Rest - LUE":1,"20. Tremor at Rest - RLE":0,
    "20. Tremor at Rest - LLE":0,
    "21. Action or Postural Tremor - RUE":1,"21. Action or Postural Tremor - LUE":1,
    "22. Rigidity - neck":1,"22. Rigidity - RUE":2,"22. Rigidity - LUE":2,
    "22. Rigidity - RLE":1,"22. Rigidity - LLE":1,
    "23.Finger Taps - RUE":2,"23.Finger Taps - LUE":1,
    "24. Hand Movements - RUE":2,"24. Hand Movements - LUE":1,
    "25. Rapid Alternating Movements - RUE":1,"25. Rapid Alternating Movements - LUE":1,
    "26. Leg Agility - RLE":1,"26. Leg Agility - LLE":1,
    "27. Arising from Chair":1,"28. Posture":1,"29. Gait":2,
    "30. Postural Stability":1,"31. Body Bradykinesia and Hypokinesia":2,
    "Entropy of speech timing (-)":1.56,"Rate of speech timing (-/min)":340,
    "Acceleration of speech timing (-/min2)":10,
    "Duration of pause intervals (ms)":160,"Duration of voiced intervals (ms)":270,
    "Gaping in-between voiced intervals (-/min)":50,
    "Duration of unvoiced stops (ms)":25,
    "Decay of unvoiced fricatives (\u2030/min)":-1.5,
    "Relative loudness of respiration (dB)":-22,
    "Pause intervals per respiration (-)":5,
    "Rate of speech respiration (-/min)":17,
    "Latency of respiratory exchange (ms)":200,
}
tf_motor = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="")
writer = csv.DictWriter(tf_motor, fieldnames=list(motor_row.keys()))
writer.writeheader(); writer.writerow(motor_row)
tf_motor.close()

r = requests.post(f"{BASE}/motor/predict",
    headers=DOC_HEADERS,
    data={"patient_id": pid},
    files={"motor_data": ("motor_test.csv", open(tf_motor.name, "rb"), "text/csv")})
check("POST /motor/predict", r, 200)
os.unlink(tf_motor.name)

# Voice — skip if no test audio available
voice_path = "tests/test_audio.wav"
if os.path.exists(voice_path):
    r = requests.post(f"{BASE}/voice/predict",
        headers=DOC_HEADERS,
        data={"patient_id": pid},
        files={"audio": ("test.wav", open(voice_path, "rb"), "audio/wav")})
    check("POST /voice/predict", r, 200)
else:
    print(f"  {YELLOW}⏭  SKIP{RESET}  POST /voice/predict  →  no test audio at {voice_path}")

# MRI — skip if no test image available
mri_path = "tests/test_mri.jpg"
if os.path.exists(mri_path):
    r = requests.post(f"{BASE}/mri/predict",
        headers=DOC_HEADERS,
        data={"patient_id": pid},
        files={"mri_scan": ("test_mri.jpg", open(mri_path, "rb"), "image/jpeg")})
    check("POST /mri/predict", r, 200)
else:
    print(f"  {YELLOW}⏭  SKIP{RESET}  POST /mri/predict  →  no test image at {mri_path}")

spiral_path = "tests/test_spiral.jpg"
if os.path.exists(spiral_path):
    r = requests.post(f"{BASE}/spiral/predict",
        headers=DOC_HEADERS,
        data={"patient_id": pid},
        files={"spiral_image": ("test_spiral.jpg", open(spiral_path, "rb"), "image/jpeg")})
    check("POST /spiral/predict", r, 200)
else:
    print(f"  {YELLOW}⏭  SKIP{RESET}  POST /spiral/predict  →  no test image at {spiral_path}")


# ─────────────────────────────────────────────────────────────
# 6. PROGRESSION ENDPOINTS
# ─────────────────────────────────────────────────────────────
section("6. Progression & Forecasting (Module 3 & 4)")

r = requests.get(f"{BASE}/progression/baseline/{pid}", headers=DOC_HEADERS)
check(f"GET /progression/baseline/{pid}", r, 200)

r = requests.get(f"{BASE}/progression/forecast/{pid}", headers=DOC_HEADERS)
j = check(f"GET /progression/forecast/{pid}", r, 200)
if j:
    d = j["data"]
    if d.get("can_forecast"):
        ok("  Forecast model type", d.get("model","—"))
        ok("  R² score", str(d.get("r_squared","—")))
        ok("  Trend", d.get("trend_label","—"))
    else:
        print(f"  {YELLOW}  ℹ  Forecast needs more data: {d.get('reason','')}{RESET}")

r = requests.get(f"{BASE}/progression/lime/{pid}/clinical", headers=DOC_HEADERS)
j = check(f"GET /progression/lime/{pid}/clinical", r, 200)
if j and j["data"].get("success"):
    n = len(j["data"].get("features", []))
    ok(f"  LIME clinical features returned", str(n))

r = requests.get(f"{BASE}/progression/lime/{pid}/voice", headers=DOC_HEADERS)
j = check(f"GET /progression/lime/{pid}/voice", r, 200)
if j and j["data"].get("success"):
    n = len(j["data"].get("features", []))
    ok(f"  LIME voice features returned", str(n))

r = requests.get(f"{BASE}/progression/summary/{pid}", headers=DOC_HEADERS)
check(f"GET /progression/summary/{pid}", r, 200)


# ─────────────────────────────────────────────────────────────
# 7. AUTH — LOGOUT
# ─────────────────────────────────────────────────────────────
section("7. Logout & Token Revocation")

r = requests.delete(f"{BASE}/auth/logout", headers=HEADERS)
check("DELETE /auth/logout", r, 200)

# Token should be revoked now
r = requests.get(f"{BASE}/auth/me", headers=HEADERS)
if r.status_code == 401:
    ok("Revoked token correctly rejected → 401")
else:
    fail("Token revocation", f"Expected 401 after logout, got {r.status_code}")


# ─────────────────────────────────────────────────────────────
# 8. ACCESS CONTROL CHECKS
# ─────────────────────────────────────────────────────────────
section("8. Access Control (RBAC)")

# No token
r = requests.get(f"{BASE}/fusion/dashboard/{pid}")
if r.status_code == 401:
    ok("No token → 401")
else:
    fail("No token check", f"Expected 401, got {r.status_code}")

# Doctor can list all patients
r = requests.get(f"{BASE}/patients/", headers=DOC_HEADERS)
check("Doctor GET /patients/ → 200", r, 200)

# Patient cannot list all patients
r = requests.post(f"{BASE}/auth/login", json={
    "email": "james.h@neurotrace.ai", "password": "Patient123!"})
if r.status_code == 200:
    pt_token = r.json()["data"]["access_token"]
    pt_headers = {"Authorization": f"Bearer {pt_token}"}
    r2 = requests.get(f"{BASE}/patients/", headers=pt_headers)
    if r2.status_code == 403:
        ok("Patient GET /patients/ → 403 correctly denied")
    else:
        fail("Patient RBAC check", f"Expected 403, got {r2.status_code}")


# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{BOLD}{'═'*55}{RESET}")
print(f"{BOLD}  RESULTS: {GREEN}{passed} passed{RESET}{BOLD} / {RED}{failed} failed{RESET}{BOLD} / {total} total{RESET}")
print(f"{BOLD}{'═'*55}{RESET}")
if failed == 0:
    print(f"\n{GREEN}{BOLD}  🎉 All endpoints are working correctly!{RESET}\n")
else:
    print(f"\n{RED}  ⚠  {failed} endpoint(s) need attention. Check the FAIL lines above.{RESET}\n")

sys.exit(0 if failed == 0 else 1)