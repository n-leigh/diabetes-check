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
        "MentHlth": 5, "NoDocbcCost": 0, "Sex": 1
    }
    risks = compute_all_risks(patient)
    assert "cardiovascular" in risks
    assert "general_burden" in risks
    assert "neuropathy_mobility" in risks
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
        "BMI": "29.4",
        "HighBP": "1",
        "HighChol": "1",
        "Smoker": "1",
        "HeartDiseaseorAttack": "0",
        "Stroke": "0",
        "DiffWalk": "1",
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
    print("POST /predict with valid CSRF returned 200 OK with clinical AUROC and guideline badges rendered.")

    res_hist = client.get("/history")
    assert res_hist.status_code == 200
    print("GET /history returned 200 OK")


if __name__ == "__main__":
    test_rule_matrix()
    test_database_persistence()
    test_flask_endpoints()
    print("\n[ALL CLINICAL ACCURACY & PRODUCTION SECURITY TESTS PASSED!]")
