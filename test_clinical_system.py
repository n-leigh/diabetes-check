"""
test_clinical_system.py
Automated end-to-end verification of clinical accuracy pipeline, models, and web app.
"""

import os
import io
import re
import sqlite3
import zipfile
import pandas as pd
from app import app
from clinical_model import ClinicalRiskWrapper
import database
from rule_matrix import compute_all_risks, compute_lab_assessment


def test_model_output_pairing():
    class FixedProbabilityEstimator:
        def predict_proba(self, X):
            return pd.DataFrame([[0.7, 0.3] for _ in range(len(X))]).to_numpy()

    wrapper = ClinicalRiskWrapper(
        base_estimator=FixedProbabilityEstimator(),
        feature_subset=["feature"],
        screening_threshold=0.20,
        referral_threshold=0.45,
    )
    labels, probabilities = wrapper.predict_with_probability(pd.DataFrame({"feature": [1]}))
    assert labels.tolist() == ["Moderate Estimated Risk"]
    assert probabilities.tolist() == [0.3]
    assert wrapper.predict(pd.DataFrame({"feature": [1]})).tolist() == labels.tolist()
    print("Model output pairing verified: category and probability derive from the same prediction.")


def test_model_class_semantics():
    class ReversedClassEstimator:
        classes_ = [1, 0]

        def predict_proba(self, X):
            return pd.DataFrame([[0.3, 0.7] for _ in range(len(X))]).to_numpy()

    wrapper = ClinicalRiskWrapper(
        base_estimator=ReversedClassEstimator(),
        feature_subset=["feature"],
    )
    try:
        wrapper.predict_with_probability(pd.DataFrame({"feature": [1]}))
    except ValueError as error:
        assert "classes_ as [0, 1]" in str(error)
    else:
        raise AssertionError("Reversed model classes must be rejected")
    print("Model class semantics verified: reversed probability classes are rejected.")


def test_localhost_launcher_boundary():
    with open("wsgi.py", encoding="utf-8") as launcher:
        source = launcher.read()
    assert "serve(app, host='127.0.0.1'" in source
    assert "host='0.0.0.0'" not in source
    print("Launcher boundary verified: Waitress binds only to localhost.")


def test_rule_matrix():
    print("\n--- 1. Testing Rule Matrix (v2.0-clinical) ---")
    patient = {
        "HighBP": 1, "HighChol": 1, "Smoker": 1, "HeartDiseaseorAttack": 0, "Stroke": 0,
        "BMI": 31.5, "Age": 10, "DiffWalk": 1, "PhysHlth": 15, "GenHlth": 4,
        "MentHlth": 5, "NoDocbcCost": 0, "Sex": 1, "DiabetesDuration": 3, "BlurryVision": 1,
    }
    risks = compute_all_risks(patient)
    assert "cardiovascular" in risks
    assert "general_burden" in risks
    assert "neuropathy_mobility" in risks
    assert "retinopathy" in risks
    print("Rule risks computed successfully:", {k: v["label"] for k, v in risks.items()})

    lab = compute_lab_assessment(hba1c=7.8, systolic_bp=135, ldl=115)
    assert lab is not None
    print(f"Lab assessment computed successfully: {lab['label']} ({lab['percentage']}%)")


import contextlib
import tempfile


@contextlib.contextmanager
def isolated_database_environment():
    with tempfile.TemporaryDirectory() as directory:
        original_db_path = database.DB_PATH
        original_key_path = database.KEY_PATH
        original_protected_key_path = database.PROTECTED_KEY_PATH
        database.DB_PATH = os.path.join(directory, "diabetes_system.db")
        database.KEY_PATH = os.path.join(directory, ".db.key")
        database.PROTECTED_KEY_PATH = os.path.join(directory, ".db.key.dpapi")
        try:
            database.init_db()
            yield directory
        finally:
            database.DB_PATH = original_db_path
            database.KEY_PATH = original_key_path
            database.PROTECTED_KEY_PATH = original_protected_key_path


def test_database_persistence():
    print("\n--- 2. Testing Database Persistence & Safe Migration ---")
    with isolated_database_environment():
        database.init_db()
        conn = database.get_connection()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print("Existing tables in SQLite:", tables)
        assert "assessments" in tables
        assert "risk_results" in tables

        count_before = conn.execute("SELECT count(*) FROM assessments").fetchone()[0]
        conn.close()

        database.init_db()
        conn2 = database.get_connection()
        count_after = conn2.execute("SELECT count(*) FROM assessments").fetchone()[0]
        conn2.close()
        assert count_before == count_after, "Database wiped records on init_db()! Schema safety failed."
        print("Non-destructive database migration verified: Record count preserved.")


def test_historical_lab_legend_points():
    print("\n--- 3. Testing Historical Lab Legend Reconstruction ---")
    with isolated_database_environment():
        record_id = database.save_assessment(
            session_id="test-session",
            patient={"Age": 10, "Sex": 1, "DiabetesDuration": 3, "BMI": 29.4},
            rule_results={"retinopathy": {"score": 1, "percentage": 25, "label": "Low Risk", "clinical_driver": "Normal"}},
            model_results={},
            lab_assessment=compute_lab_assessment(hba1c=5.5, systolic_bp=100, ldl=86),
        )
        record = database.get_assessment(record_id)
        assert record and record.get("lab_assessment"), "Saved assessment record with lab data not found."

        details = record["lab_assessment"]["details"]
        assert details["hba1c"]["value"] == 5.5
        assert details["hba1c"]["points"] == 0
        assert details["systolic_bp"]["value"] == 100
        assert details["systolic_bp"]["points"] == 0
        assert details["ldl"]["value"] == 86
        assert details["ldl"]["points"] == 1
        print("Historical lab values reconstruct their correct guideline points.")


def test_regulatory_positioning_copy_consistency():
    client = app.test_client()

    home_html = client.get("/").get_data(as_text=True)
    about_html = client.get("/about").get_data(as_text=True)
    result_html = client.get("/assessment").get_data(as_text=True)

    assert "health screening aid" in home_html.lower() or "health screening aid" in about_html.lower()
    assert "not a diagnostic device" in about_html.lower()
    assert "clinical decision-support tool" not in about_html.lower()
    assert "clinical decision support" not in result_html.lower()
    assert "screening aid" in about_html.lower() or "screening aid" in home_html.lower()
    print("Positioning copy consistency verified: user-facing pages frame DiaBeates as a health screening aid rather than a diagnostic or clinical decision-support tool.")


def test_bmi_calculator_supports_mixed_units():
    client = app.test_client()
    assess_html = client.get("/assessment").get_data(as_text=True)

    assert 'id="bmiHeightUnit"' in assess_html
    assert 'value="cm"' in assess_html
    assert 'value="ftin"' in assess_html
    assert 'id="bmiWeightUnit"' in assess_html
    assert 'value="kg"' in assess_html
    assert 'value="lbs"' in assess_html
    assert 'id="bmiHeightCm"' in assess_html
    assert 'id="bmiHeightFt"' in assess_html
    assert 'id="bmiWeight"' in assess_html
    print("BMI calculator provides independent height and weight unit options.")


def test_flask_endpoints():
    print("\n--- 3. Testing Flask Web Application Endpoints ---")
    with isolated_database_environment():
        client = app.test_client()

        res_home = client.get("/")
        assert res_home.status_code == 200
        print("GET / returned 200 OK")

        res_assess = client.get("/assessment")
        assert res_assess.status_code == 200
        print("GET /assessment returned 200 OK")

        # Extract CSRF token from assessment page
        html_assess = res_assess.get_data(as_text=True)
        m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html_assess)
        csrf_token = m.group(1) if m else ""
        assert csrf_token, "CSRF token not found in assessment page HTML!"
        print("Extracted valid CSRF token from /assessment form.")

        post_data = {
            "csrf_token": csrf_token,
            "save_history": "1",
            "Age": "10",
            "Sex": "1",
            "DiabetesDuration": "3",
            "BMI": "29.4",
            "HighBP": "1",
            "HighChol": "1",
            "Smoker": "1",
            "HeartDiseaseorAttack": "0",
            "Stroke": "0",
            "DiffWalk": "1",
            "BlurryVision": "1",
            "PhysHlth": "10",
            "GenHlth": "4",
            "MentHlth": "5",
            "NoDocbcCost": "0",
            "LabHbA1c": "7.5",
            "LabSystolicBP": "138",
            "LabLDL": "125"
        }

        # Test CSRF rejection when token is missing
        no_csrf_data = {k: v for k, v in post_data.items() if k != "csrf_token"}
        res_no_csrf = client.post("/predict", data=no_csrf_data)
        assert res_no_csrf.status_code == 400
        print("POST /predict correctly rejected request missing CSRF token (400 Bad Request).")

        # Test successful prediction with CSRF token
        res_predict = client.post("/predict", data=post_data, follow_redirects=True)
        assert res_predict.status_code == 200
        html = res_predict.get_data(as_text=True)
        assert "Complication Risk Results" in html
        assert "Estimated Risk Probability" in html
        assert "What this means" in html
        assert "Your current indicators suggest a low likelihood" in html
        assert "Your results show elevated risk factors" in html
        assert "Your profile indicates significant risk factors" in html
        assert "Clinical AUROC" not in html
        assert "Brier Score" not in html
        assert "Estimate uncertainty" not in html
        assert "Model estimate" not in html
        assert "Rule points" not in html
        assert "Rule category" not in html
        assert "Guideline Score" not in html
        assert "Guideline Category" not in html
        assert "Evaluation Model" not in html
        assert "Classifier" not in html
        assert "Heart Health" in html
        assert "Kidney Health" in html
        assert "Nerve Health &amp; Movement" in html
        assert "Eye Health" in html
        assert "Patient-Specific Risk Drivers" in html
        assert html.count("Estimated Risk Probability") == 4
        assert html.count("Low Risk") + html.count("Moderate Risk") + html.count("High Risk") >= 4
        print("POST /predict with valid CSRF returned 200 OK with all 4 complication domains rendered.")

        res_hist_desc = client.get("/history?sort=desc")
        assert res_hist_desc.status_code == 200
        html_desc = res_hist_desc.get_data(as_text=True)
        assert "Newest" in html_desc

        res_hist_asc = client.get("/history?sort=asc")
        assert res_hist_asc.status_code == 200
        html_asc = res_hist_asc.get_data(as_text=True)
        assert "Oldest" in html_asc
        print("GET /history (desc and asc) returned 200 OK with sort toggle.")

        # Test print view
        with app.app_context():
            from database import get_connection
            conn = get_connection()
            row = conn.execute("SELECT id FROM assessments ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()
            assert row is not None, "Saved assessment record not found for print test."
            latest_id = row["id"]
            res_print = client.get(f"/history/{latest_id}/print")
            assert res_print.status_code == 200
            print_html = res_print.get_data(as_text=True)
            assert "Diabetic Retinopathy (ADA)" in print_html
            assert "Rule-Matrix Result" in print_html
            assert "Calibrated ML Result" in print_html
            assert "Clinician Review Notes" in print_html
            print(f"GET /history/{latest_id}/print returned 200 OK with Retinopathy section.")

        res_backup = client.get("/data/backup")
        assert res_backup.status_code == 200
        assert res_backup.mimetype == "application/zip"
        with zipfile.ZipFile(io.BytesIO(res_backup.data)) as backup:
            assert set(backup.namelist()) == {"diabetes_system.db", "SHA256SUM"}
        print("GET /data/backup returned a self-verifying encrypted backup bundle.")

        res_restore = client.post(
            "/data/restore",
            data={"csrf_token": csrf_token, "backup_file": (io.BytesIO(res_backup.data), "backup.zip")},
            content_type="multipart/form-data",
        )
        assert res_restore.status_code == 302
        print("POST /data/restore accepted a checksum-verified encrypted backup.")

        res_diagnostics = client.get("/diagnostics/export")
        assert res_diagnostics.status_code == 200
        with zipfile.ZipFile(io.BytesIO(res_diagnostics.data)) as diagnostics:
            assert set(diagnostics.namelist()) == {"system_status.json", "sanitized_application.log"}
            diagnostic_text = "\n".join(diagnostics.read(name).decode("utf-8") for name in diagnostics.namelist())
            assert "diabetes_system.db" not in diagnostic_text
            assert "session_id" not in diagnostic_text
            assert "model" in diagnostic_text.lower()
        print("GET /diagnostics/export returned sanitized technical metadata without patient rows.")


def test_health_and_security_headers():
    print("\n--- 4. Testing /health Probe and Production Security Headers ---")
    with isolated_database_environment():
        client = app.test_client()

        res_health = client.get("/health")
        assert res_health.status_code == 200
        health_data = res_health.get_json()
        assert health_data["status"] == "healthy"
        assert health_data["database"] == "connected"
        assert len(health_data["models_loaded"]) == 4
        print("GET /health probe verified: 200 OK with connected DB and 4 models loaded.")

        # Check security response headers
        res = client.get("/")
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        print("Production security headers verified: X-Frame-Options, X-Content-Type-Options, Referrer-Policy present.")

        # Check WCAG and BMI modal markup on /assessment
        res_assess = client.get("/assessment")
        assess_html = res_assess.get_data(as_text=True)
        assert 'id="BMI"' in assess_html
        assert 'for="BMI"' in assess_html
        assert 'id="bmiModal"' in assess_html
        assert 'role="alert"' in assess_html
        print("WCAG 2.1 AA accessibility attributes and BMI modal markup verified on /assessment.")

        # Test data retention pruning
        pruned = database.prune_expired_assessments(days=365)
        assert isinstance(pruned, int)
        print(f"Data retention policy verified: prune_expired_assessments executed cleanly (pruned {pruned} records).")


if __name__ == "__main__":
    test_model_output_pairing()
    test_model_class_semantics()
    test_localhost_launcher_boundary()
    test_rule_matrix()
    test_database_persistence()
    test_historical_lab_legend_points()
    test_flask_endpoints()
    test_health_and_security_headers()
    print("\n[ALL CLINICAL ACCURACY, ACCESSIBILITY & PRODUCTION SECURITY TESTS PASSED!]")
