"""
live_browser_test.py
Performs live HTTP browser simulation against http://127.0.0.1:5000
with cookies, CSRF tokens, form submission, and results verification.
"""

import urllib.request
import urllib.parse
import http.cookiejar
import re

BASE_URL = "http://127.0.0.1:5000"

def run_live_browser_test():
    print("=" * 70)
    print("STARTING LIVE BROWSER SIMULATION TEST ON", BASE_URL)
    print("=" * 70)

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    # 1. Landing page
    print("\n[Step 1] Loading Landing Page (GET /)...")
    req = urllib.request.Request(f"{BASE_URL}/", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with opener.open(req, timeout=5) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        html_home = resp.read().decode("utf-8")
        assert "DiaBeates" in html_home
        assert "Start Risk Assessment" in html_home
        print("  -> SUCCESS: Landing page loaded successfully (200 OK)")

    # 2. Assessment Form
    print("\n[Step 2] Loading Assessment Form (GET /assessment)...")
    req = urllib.request.Request(f"{BASE_URL}/assessment", headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=5) as resp:
        assert resp.status == 200
        html_assess = resp.read().decode("utf-8")
        m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html_assess)
        assert m, "CSRF token not found on assessment page!"
        csrf_token = m.group(1)
        print(f"  -> SUCCESS: Form loaded. Extracted CSRF token: {csrf_token[:16]}...")

    # 3. Patient Submission
    print("\n[Step 3] Submitting Patient Profile (POST /predict)...")
    patient_payload = {
        "csrf_token": csrf_token,
        "Age": "9",            # 60-64 years
        "Sex": "1",            # Male
        "BMI": "31.2",         # Obese
        "HighBP": "1",         # Hypertension: Yes
        "HighChol": "1",       # High Cholesterol: Yes
        "Smoker": "1",         # Smoker: Yes
        "HeartDiseaseorAttack": "0",
        "Stroke": "0",
        "DiffWalk": "1",       # Difficulty walking: Yes
        "PhysHlth": "12",      # 12 days poor physical health
        "GenHlth": "4",        # Fair general health
        "MentHlth": "6",
        "NoDocbcCost": "0",
        "LabHbA1c": "7.6",     # 7.6% (suboptimal)
        "LabSystolicBP": "138",# 138 mmHg (elevated)
        "LabLDL": "120"        # 120 mg/dL (borderline)
    }

    data_encoded = urllib.parse.urlencode(patient_payload).encode("utf-8")
    req_post = urllib.request.Request(
        f"{BASE_URL}/predict",
        data=data_encoded,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{BASE_URL}/assessment"
        }
    )

    with opener.open(req_post, timeout=5) as resp:
        assert resp.status == 200
        html_result = resp.read().decode("utf-8")

        # Verify Complication Cards
        assert "Cardiovascular (ACC/AHA)" in html_result, "Cardiovascular card missing!"
        assert "Nephropathy & Renal (KDIGO)" in html_result, "Nephropathy card missing!"
        assert "Neuropathy & Mobility (MNSI)" in html_result, "Neuropathy card missing!"
        assert "Clinical AUROC" in html_result, "Clinical AUROC score missing!"
        print("  -> SUCCESS: All three clinical complication cards rendered with AUROC scores.")

        # Verify Lab Panel
        assert "7.6%" in html_result, "HbA1c lab value missing!"
        assert "138 mmHg" in html_result, "Systolic BP lab value missing!"
        assert "120 mg/dL" in html_result, "LDL lab value missing!"
        print("  -> SUCCESS: Lab-Based Clinical Assessment panel verified (HbA1c: 7.6%, BP: 138, LDL: 120).")

        # Extract assessment ID
        m_id = re.search(r'/history/(\d+)/print', html_result)
        assert m_id, "Assessment ID link not found on result page!"
        assessment_id = m_id.group(1)
        print(f"  -> SUCCESS: Assessment persisted with ID: #{assessment_id}")

    # 4. Printable Medical Report View
    print(f"\n[Step 4] Checking Printable Clinical Report (GET /history/{assessment_id}/print)...")
    req_print = urllib.request.Request(f"{BASE_URL}/history/{assessment_id}/print", headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req_print, timeout=5) as resp:
        assert resp.status == 200
        html_print = resp.read().decode("utf-8")
        assert "DiaBeates" in html_print
        assert "Print / Save PDF" in html_print or "window.print()" in html_print
        print("  -> SUCCESS: Print view rendered cleanly with patient summary and print trigger.")

    # 5. History Page Verification
    print("\n[Step 5] Checking Session History Page (GET /history)...")
    req_hist = urllib.request.Request(f"{BASE_URL}/history", headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req_hist, timeout=5) as resp:
        assert resp.status == 200
        html_history = resp.read().decode("utf-8")
        assert f"/history/{assessment_id}" in html_history, "Newly saved assessment missing from history table!"
        print("  -> SUCCESS: History table verified. Saved assessment is accessible.")

    print("\n" + "=" * 70)
    print("[ALL LIVE END-TO-END BROWSER VERIFICATION CHECKS PASSED 100%]")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_live_browser_test()
