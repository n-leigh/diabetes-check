"""
test_privacy_hardening.py
Automated test suite verifying privacy hardening, CSP policies, session scoping,
export/clear endpoints, and local data persistence controls for DiaBeates.
"""

import contextlib
import json
import os
import re
import tempfile

from app import app
import database


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


def get_csrf_token(client, url="/assessment"):
    res = client.get(url)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    assert m, f"CSRF token not found in {url} HTML"
    return m.group(1)


def get_sample_patient_payload(csrf_token, save_history=False):
    payload = {
        "csrf_token": csrf_token,
        "Age": "9",
        "Sex": "1",
        "DiabetesDuration": "2",
        "BMI": "27.5",
        "HighBP": "1",
        "HighChol": "0",
        "Smoker": "0",
        "HeartDiseaseorAttack": "0",
        "Stroke": "0",
        "DiffWalk": "0",
        "BlurryVision": "0",
        "PhysHlth": "2",
        "GenHlth": "3",
        "MentHlth": "1",
        "NoDocbcCost": "0",
        "LabHbA1c": "6.8",
        "LabSystolicBP": "128",
        "LabLDL": "110",
    }
    if save_history:
        payload["save_history"] = "1"
    return payload


def test_csp_headers_and_no_external_sources():
    """Verify strict Content Security Policy on all public routes."""
    client = app.test_client()
    routes = ["/", "/assessment", "/about", "/report", "/history"]

    for route in routes:
        res = client.get(route)
        assert res.status_code == 200
        csp = res.headers.get("Content-Security-Policy", "")
        assert csp, f"Missing Content-Security-Policy header on {route}"

        # Assert zero unsafe-inline and zero unsafe-eval
        assert "'unsafe-inline'" not in csp, f"Found 'unsafe-inline' in CSP on {route}"
        assert "'unsafe-eval'" not in csp, f"Found 'unsafe-eval' in CSP on {route}"

        # Assert strict self policies
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "connect-src 'self'" in csp
        assert "img-src 'self' data:" in csp
        assert "font-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp

        # Assert absence of remote CDN domains
        for forbidden in ["cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com", "unsplash.com"]:
            assert forbidden not in csp, f"Forbidden remote origin {forbidden} found in CSP on {route}"

    print("Strict Content-Security-Policy verified across all routes (no unsafe-inline, no external CDNs).")


def test_no_external_assets_in_templates():
    """Scan all HTML templates to ensure zero external scripts, stylesheets, fonts, or images."""
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    external_domains = ["cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com", "images.unsplash.com"]

    for root, _, files in os.walk(templates_dir):
        for f in files:
            if f.endswith(".html"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
                    for domain in external_domains:
                        assert domain not in content, f"Found external domain '{domain}' in {path}"
                    # Check for inline event handlers (onclick=, onload=, onchange=, onsubmit=)
                    event_handlers = re.findall(r'\bon[a-z]+\s*=', content, re.IGNORECASE)
                    assert not event_handlers, f"Found inline event handlers {event_handlers} in {path}"

    print("Template inspection verified: zero external asset domains and zero inline event handlers.")


def test_optional_assessment_save_behavior():
    """Test that assessments are saved to DB ONLY when save_history is explicitly checked."""
    with isolated_database_environment():
        client = app.test_client()
        csrf_token = get_csrf_token(client, "/assessment")

        # 1. Unchecked save assessment (default)
        payload_no_save = get_sample_patient_payload(csrf_token, save_history=False)
        res1 = client.post("/predict", data=payload_no_save)
        assert res1.status_code == 200
        html1 = res1.get_data(as_text=True)
        assert "Complication Risk Results" in html1
        assert "Unsaved In-Memory Assessment" in html1

        conn = database.get_connection()
        count1 = conn.execute("SELECT count(*) FROM assessments").fetchone()[0]
        conn.close()
        assert count1 == 0, f"Expected 0 records in database when save_history is off, found {count1}"

        # 2. Checked save assessment
        # Need a fresh CSRF token or session
        csrf_token2 = get_csrf_token(client, "/assessment")
        payload_with_save = get_sample_patient_payload(csrf_token2, save_history=True)
        res2 = client.post("/predict", data=payload_with_save)
        assert res2.status_code == 200
        html2 = res2.get_data(as_text=True)
        assert "Complication Risk Results" in html2
        assert "Unsaved In-Memory Assessment" not in html2

        conn = database.get_connection()
        count2 = conn.execute("SELECT count(*) FROM assessments").fetchone()[0]
        row = conn.execute("SELECT id, session_id, bmi FROM assessments LIMIT 1").fetchone()
        conn.close()
        assert count2 == 1, f"Expected 1 record in database when save_history is on, found {count2}"
        assert row["bmi"] == 27.5
        assert row["session_id"] is not None

    print("Optional save behavior verified: records written only when explicitly opted in.")


def test_archive_assessment_endpoint():
    """Test POST /history/<id>/archive security, CSRF validation, and session scoping (Process 5.3)."""
    with isolated_database_environment():
        # Set up Session A with 1 assessment
        client_a = app.test_client()
        csrf_a = get_csrf_token(client_a, "/assessment")
        post_a = get_sample_patient_payload(csrf_a, save_history=True)
        client_a.post("/predict", data=post_a)

        conn = database.get_connection()
        row_a = conn.execute("SELECT id FROM assessments ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        id_a = row_a["id"]

        # Missing CSRF rejected
        res_no_csrf = client_a.post(f"/history/{id_a}/archive", data={"archived": "1"})
        assert res_no_csrf.status_code == 400

        # Session B cannot archive Session A's record
        client_b = app.test_client()
        csrf_b = get_csrf_token(client_b, "/assessment")
        client_b.post(f"/history/{id_a}/archive", data={"csrf_token": csrf_b, "archived": "1"})
        conn = database.get_connection()
        check_a = conn.execute("SELECT archived FROM assessments WHERE id = ?", (id_a,)).fetchone()
        conn.close()
        assert check_a["archived"] == 0, "Cross-session archive mutation succeeded unexpectedly!"

        # Session A successfully archives own record
        res_archive_a = client_a.post(f"/history/{id_a}/archive", data={"csrf_token": csrf_a, "archived": "1"}, follow_redirects=True)
        assert res_archive_a.status_code == 200
        conn = database.get_connection()
        check_a_archived = conn.execute("SELECT archived FROM assessments WHERE id = ?", (id_a,)).fetchone()
        conn.close()
        assert check_a_archived["archived"] == 1

    print("POST /history/<id>/archive verified: strict CSRF enforcement and session isolation (Process 5.3).")


def test_delete_assessment_endpoint():
    """Test POST /history/<id>/delete security, CSRF validation, and session scoping (Process 5.4)."""
    with isolated_database_environment():
        # Set up Session A with 1 assessment
        client_a = app.test_client()
        csrf_a = get_csrf_token(client_a, "/assessment")
        post_a = get_sample_patient_payload(csrf_a, save_history=True)
        client_a.post("/predict", data=post_a)

        conn = database.get_connection()
        row_a = conn.execute("SELECT id FROM assessments ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        id_a = row_a["id"]

        # Missing CSRF rejected
        res_no_csrf = client_a.post(f"/history/{id_a}/delete")
        assert res_no_csrf.status_code == 400

        # Session B cannot delete Session A's record
        client_b = app.test_client()
        csrf_b = get_csrf_token(client_b, "/assessment")
        client_b.post(f"/history/{id_a}/delete", data={"csrf_token": csrf_b})
        conn = database.get_connection()
        check_a = conn.execute("SELECT id FROM assessments WHERE id = ?", (id_a,)).fetchone()
        conn.close()
        assert check_a is not None, "Cross-session deletion succeeded unexpectedly!"

        # Session A successfully deletes own record
        res_delete_a = client_a.post(f"/history/{id_a}/delete", data={"csrf_token": csrf_a}, follow_redirects=True)
        assert res_delete_a.status_code == 200
        conn = database.get_connection()
        check_deleted = conn.execute("SELECT id FROM assessments WHERE id = ?", (id_a,)).fetchone()
        conn.close()
        assert check_deleted is None

    print("POST /history/<id>/delete verified: strict CSRF enforcement and session isolation (Process 5.4).")


def test_report_viewer_endpoint():
    """Verify GET /report returns clean standalone shell with no PHI or server-side state."""
    client = app.test_client()
    res = client.get("/report")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "report_viewer.js" in html
    assert "reportRoot" in html
    assert "passphrasePromptModal" in html
    assert "reportPassphraseInput" in html
    # Ensure no patient data is embedded in the response
    assert "LabHbA1c" not in html
    assert "Patient-Specific Risk Drivers" not in html
    print("GET /report verified: clean client-side shell returned with zero embedded medical data.")


if __name__ == "__main__":
    test_csp_headers_and_no_external_sources()
    test_no_external_assets_in_templates()
    test_optional_assessment_save_behavior()
    test_archive_assessment_endpoint()
    test_delete_assessment_endpoint()
    test_report_viewer_endpoint()
    print("\n[ALL PRIVACY HARDENING & DATA ISOLATION TESTS PASSED!]")

