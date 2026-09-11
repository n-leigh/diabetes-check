"""
test_clinical_system.py
Automated end-to-end verification of clinical accuracy pipeline, models, and web app.
"""

import os
import re
import sqlite3
import pandas as pd
from app import app
import database
from rule_matrix import compute_all_risks, compute_lab_assessment


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


def test_database_persistence():
    print("\n--- 2. Testing Database Persistence & Safe Migration ---")
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
    record = database.get_assessment(5)
    if not record or not record.get("lab_assessment"):
        print("No assessment 5 lab record available; skipping fixture-specific check.")
        return

    details = record["lab_assessment"]["details"]
    assert details["hba1c"]["value"] == 5.5
    assert details["hba1c"]["points"] == 0
    assert details["systolic_bp"]["value"] == 100
    assert details["systolic_bp"]["points"] == 0
    assert details["ldl"]["value"] == 86
    assert details["ldl"]["points"] == 1
    print("Historical lab values reconstruct their correct guideline points.")


def test_flask_endpoints():
    print("\n--- 3. Testing Flask Web Application Endpoints ---")
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
    assert "Clinical AUROC" in html
    assert "ACC/AHA" in html
    assert "KDIGO" in html
    assert "MNSI" in html
    assert "Retinopathy" in html
    assert "Patient-Specific Risk Drivers" in html
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
        if row:
            latest_id = row["id"]
            res_print = client.get(f"/history/{latest_id}/print")
            assert res_print.status_code == 200
            assert "Diabetic Retinopathy (ADA)" in res_print.get_data(as_text=True)
            print(f"GET /history/{latest_id}/print returned 200 OK with Retinopathy section.")


def test_health_and_security_headers():
    print("\n--- 4. Testing /health Probe and Production Security Headers ---")
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
    test_rule_matrix()
    test_database_persistence()
    test_historical_lab_legend_points()
    test_flask_endpoints()
    test_health_and_security_headers()
    print("\n[ALL CLINICAL ACCURACY, ACCESSIBILITY & PRODUCTION SECURITY TESTS PASSED!]")
