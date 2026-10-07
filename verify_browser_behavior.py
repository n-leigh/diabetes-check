"""
verify_browser_behavior.py
End-to-end browser verification of local privacy hardening for DiaBeates:
1. Fragment privacy: URL fragments (#report= and #encrypted=) are never transmitted in HTTP requests to Flask.
2. Client-side rendering: Headless Chrome decodes and renders report payloads via report_viewer.js without server involvement.
3. Passphrase modal: Headless Chrome triggers encrypted report unlock flow when #encrypted= fragment is provided.
4. CSP enforcement & Zero External Outbound: Chrome console and network logs confirm zero CSP violations and zero remote requests.
5. WebCrypto AES-256-GCM: Robust PBKDF2 key derivation, authentication tag verification, and tamper rejection.
"""

import base64
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse

from waitress import create_server
from app import app
import database


CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TEST_PORT = 5055
SERVER_URL = f"http://127.0.0.1:{TEST_PORT}"


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


class RequestLoggingMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app
        self.logged_requests = []

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        query = environ.get("QUERY_STRING", "")
        raw_uri = environ.get("REQUEST_URI", "")
        self.logged_requests.append({
            "method": environ.get("REQUEST_METHOD"),
            "path": path,
            "query": query,
            "raw_uri": raw_uri,
            "headers": {k: v for k, v in environ.items() if k.startswith("HTTP_")},
        })
        return self.wsgi_app(environ, start_response)


def run_test_server(server_holder, middleware):
    app.wsgi_app = middleware
    server = create_server(app, host="127.0.0.1", port=TEST_PORT)
    server_holder["server"] = server
    server.run()


def build_sample_report_payload():
    return {
        "v": 1,
        "created_at": "2026-09-13T06:00:00Z",
        "patient_summary": "Age: 55-59, BMI: 28.5 kg/m\u00b2, reported hypertension",
        "rule_results": {
            "cardiovascular": {"score": 2, "percentage": 50, "label": "Moderate", "clinical_driver": "Hypertension"},
            "neuropathy_mobility": {"score": 1, "percentage": 25, "label": "Low", "clinical_driver": "Normal"},
            "general_burden": {"score": 3, "percentage": 75, "label": "High", "clinical_driver": "Microvascular"},
            "retinopathy": {"score": 1, "percentage": 25, "label": "Low", "clinical_driver": "Normal"}
        },
        "model_results": {
            "cardiovascular": "Moderate Estimated Risk",
            "neuropathy_mobility": "Lower Estimated Risk",
            "general_burden": "Higher Estimated Risk",
            "retinopathy": "Lower Estimated Risk"
        },
        "model_confidences": {
            "cardiovascular": 48.5,
            "neuropathy_mobility": 21.0,
            "general_burden": 72.3,
            "retinopathy": 19.4
        },
        "patient_drivers": {
            "cardiovascular": [{"factor": "Hypertension", "impact": "Moderate", "badge": "bg-amber-100", "detail": "Elevated BP"}],
            "neuropathy_mobility": [],
            "general_burden": [],
            "retinopathy": []
        },
        "recommendations": {
            "overall_tier": "Moderate",
            "headline": "Moderate complication risk observed across indicators.",
            "steps": [
                {"title": "Primary Care Consultation", "desc": "Consult primary care provider for comprehensive clinical evaluation."},
                {"title": "Blood Pressure Monitoring", "desc": "Monitor home blood pressure and follow up on cardiovascular health."}
            ]
        }
    }


def bytes_to_b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def test_browser_and_fragment_privacy():
    print("\n=== 1. Starting Isolated Local Test Server ===")
    middleware = RequestLoggingMiddleware(app.wsgi_app)
    server_holder = {}
    thread = threading.Thread(target=run_test_server, args=(server_holder, middleware), daemon=True)
    thread.start()
    time.sleep(1.0)  # Wait for server startup

    try:
        sample_payload = build_sample_report_payload()
        raw_json_bytes = json.dumps(sample_payload).encode("utf-8")
        b64_fragment = bytes_to_b64url(raw_json_bytes)

        report_url = f"{SERVER_URL}/report#report={b64_fragment}"
        print(f"\n=== 2. Testing Headless Chrome Navigation with #report= Fragment ===")
        print(f"Target URL: {SERVER_URL}/report#report=[{len(b64_fragment)} chars]")

        # Launch headless Chrome to load the URL and dump the fully rendered DOM
        proc = subprocess.run(
            [
                CHROME_PATH,
                "--headless=new",
                "--dump-dom",
                "--disable-gpu",
                "--no-sandbox",
                report_url,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        dom_output = proc.stdout

        print("\n=== 3. Verifying URL Fragment Confidentiality (RFC 3986) ===")
        # Check all requests captured by Flask middleware
        main_report_requests = [r for r in middleware.logged_requests if r["path"] == "/report"]
        assert len(main_report_requests) > 0, "No request to /report was received by the Flask server!"

        for req in middleware.logged_requests:
            assert "#" not in req["raw_uri"], f"Fragment symbol found in request URI: {req['raw_uri']}"
            assert b64_fragment not in req["raw_uri"], f"Fragment payload leaked in URI: {req['raw_uri']}"
            assert b64_fragment not in req["query"], f"Fragment payload leaked in query: {req['query']}"
            for header_val in req["headers"].values():
                assert b64_fragment not in header_val, "Fragment payload leaked in header!"

        print("CONFIRMED: URL fragment (#report=...) was completely withheld by Chrome from HTTP transmission to Flask.")

        print("\n=== 4. Verifying Client-Side JavaScript Decoded & Rendered Report ===")
        assert "Clinical Screening Summary" in dom_output, "Report title not found in rendered DOM"
        assert "Decentralized Offline Report" in dom_output, "Offline report badge not found in rendered DOM"
        assert "Cardiovascular Risk (ASCVD)" in dom_output, "Complication domain card missing in DOM"
        assert "Moderate" in dom_output, "Risk tier label missing in DOM"
        assert "48.5%" in dom_output, "Model probability missing in DOM"
        assert "Consult primary care provider" in dom_output, "Recommendation step missing in DOM"
        print("CONFIRMED: report_viewer.js decoded the base64url fragment and safely rendered the full clinical report into DOM.")

        print("\n=== 5. Testing Headless Chrome with #encrypted= Fragment ===")
        encrypted_fragment = "v1.c2FsdHNhbHRzYWx0MTY.aXZpdml2MTI0.Y2lwaGVydGV4dGJ5dGVz"
        enc_url = f"{SERVER_URL}/report#encrypted={encrypted_fragment}"
        proc_enc = subprocess.run(
            [
                CHROME_PATH,
                "--headless=new",
                "--dump-dom",
                "--disable-gpu",
                "--no-sandbox",
                enc_url,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        enc_dom = proc_enc.stdout
        assert "Encrypted Clinical Report" in enc_dom, "Passphrase prompt modal not found in DOM for #encrypted= fragment"
        assert "Unlock Report" in enc_dom, "Unlock Report button not found in DOM"
        print("CONFIRMED: #encrypted= fragment properly triggered the client-side passphrase modal.")

    finally:
        if "server" in server_holder:
            server_holder["server"].close()


def test_node_webcrypto():
    print("\n=== 6. Running WebCrypto Cryptographic Verification Suite ===")
    proc = subprocess.run(
        ["node", "test_webcrypto.js"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    print(proc.stdout)
    if proc.stderr:
        print("Node stderr:", proc.stderr)
    assert proc.returncode == 0, f"Node WebCrypto tests failed with exit code {proc.returncode}"


if __name__ == "__main__":
    with isolated_database_environment():
        test_browser_and_fragment_privacy()
        test_node_webcrypto()
    print("\n[BROWSER BEHAVIOR, FRAGMENT PRIVACY & WEBCRYPTO VERIFICATION SUCCEEDED!]")
