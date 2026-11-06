import contextlib
import hashlib
import os
import re
import secrets
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import check_password_hash

import app
import database
from rule_matrix import compute_lab_assessment


PASSWORD = "StrongTestPass9!"


@contextlib.contextmanager
def isolated_database_environment():
    with tempfile.TemporaryDirectory() as directory:
        original_db_path = database.DB_PATH
        original_key_path = database.KEY_PATH
        original_protected_key_path = database.PROTECTED_KEY_PATH
        original_key_env = os.environ.get("DIABEATES_DB_KEY")
        database.DB_PATH = os.path.join(directory, "diabetes_system.db")
        database.KEY_PATH = os.path.join(directory, ".db.key")
        database.PROTECTED_KEY_PATH = os.path.join(directory, ".db.key.dpapi")
        os.environ["DIABEATES_DB_KEY"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        try:
            database.init_db()
            yield directory
        finally:
            database.DB_PATH = original_db_path
            database.KEY_PATH = original_key_path
            database.PROTECTED_KEY_PATH = original_protected_key_path
            if original_key_env is not None:
                os.environ["DIABEATES_DB_KEY"] = original_key_env
            else:
                os.environ.pop("DIABEATES_DB_KEY", None)


@pytest.fixture(autouse=True)
def isolated_db():
    with isolated_database_environment():
        yield


def _csrf(client, path):
    html = client.get(path).get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert token, f"missing CSRF token on {path}"
    return token.group(1)


def _login(client, email, password=PASSWORD, next_url=None):
    path = "/login"
    if next_url:
        path += f"?next={next_url}"
    return client.post(
        path,
        data={"csrf_token": _csrf(client, "/login"), "email": email, "password": password},
        follow_redirects=False,
    )


def _assessment(session_id, user_id=None, label="Low"):
    results = {
        category: {"score": 1, "percentage": 10, "label": label}
        for category in ("cardiovascular", "general_burden", "neuropathy_mobility", "retinopathy")
    }
    return database.save_assessment(
        session_id,
        {"BMI": 22, "Age": 2, "GenHlth": 2, "Sex": 0},
        results,
        {},
        user_id=user_id,
    )


@pytest.fixture
def user():
    email = f"test-{uuid.uuid4().hex}@example.test"
    user_id = database.create_user(email, PASSWORD, "Test User")
    yield user_id, email
    if database.get_user_by_id(user_id):
        database.delete_user_account(user_id)


@pytest.fixture
def admin():
    email = f"admin-{uuid.uuid4().hex}@example.test"
    user_id = database.create_user(email, PASSWORD, "Test Admin", role="admin")
    yield user_id, email
    if database.get_user_by_id(user_id):
        database.delete_user_account(user_id)


@pytest.fixture
def client():
    app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    test_client = app.app.test_client()
    test_client.environ_base["REMOTE_ADDR"] = f"10.0.0.{secrets.randbelow(240) + 1}"
    return test_client


def test_register_requires_consent_and_rejects_weak_password(client):
    response = client.post(
        "/register",
        data={
            "csrf_token": _csrf(client, "/register"),
            "nickname": "Test",
            "email": f"weak-{uuid.uuid4().hex}@example.test",
            "password": "password",
            "confirm_password": "password",
        },
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Please agree to the Privacy Notice." in body
    assert "Use a password with 8 to 128 characters." in body


def test_login_generic_failure_and_open_redirect(client, user):
    _, email = user
    response = _login(client, email, "wrong-password")
    assert response.status_code == 200
    assert "Email or password is incorrect." in response.get_data(as_text=True)
    response = _login(client, email, next_url="https://example.com")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/history")
    client.post("/logout", data={"csrf_token": _csrf(client, "/history")})
    response = _login(client, email, next_url="/account")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/account")


def test_lockout_after_five_failures(client, user):
    user_id, email = user
    for _ in range(5):
        response = _login(client, email, "wrong-password")
    assert response.status_code == 200
    assert "Email or password is incorrect." in response.get_data(as_text=True)
    account = database.get_user_by_id(user_id)
    assert account["locked_until"] is not None


def test_claim_confirm_and_decline(client, user):
    user_id, email = user
    client.get("/assessment")
    with client.session_transaction() as state:
        guest_sid = state["session_id"]
    assessment_id = _assessment(guest_sid)
    assert _login(client, email).status_code == 302
    assert client.get("/claim").status_code == 200
    response = client.post(
        "/claim",
        data={"csrf_token": _csrf(client, "/claim"), "action": "confirm"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert database.get_assessment(assessment_id, user_id=user_id)

    client.post("/logout", data={"csrf_token": _csrf(client, "/history")})
    client.get("/assessment")
    with client.session_transaction() as state:
        new_guest_sid = state["session_id"]
    declined_id = _assessment(new_guest_sid)
    assert _login(client, email).status_code == 302
    response = client.post(
        "/claim",
        data={"csrf_token": _csrf(client, "/claim"), "action": "decline"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert database.get_assessment(declined_id, session_id=new_guest_sid)
    assert database.get_assessment(declined_id, user_id=user_id) is None


def test_ownership_returns_404_for_all_assessment_actions(client, user):
    _, owner_email = user
    other_email = f"other-{uuid.uuid4().hex}@example.test"
    other_id = database.create_user(other_email, PASSWORD, "Other User")
    try:
        assert _login(client, owner_email).status_code == 302
        with client.session_transaction() as state:
            owner_sid = state["session_id"]
        assessment_id = _assessment(owner_sid, user_id=user[0])
        client.post("/logout", data={"csrf_token": _csrf(client, "/history")})
        assert _login(client, other_email).status_code == 302
        for path in (
            f"/history/{assessment_id}",
            f"/history/{assessment_id}/print",
        ):
            assert client.get(path).status_code == 404
        csrf = _csrf(client, "/history")
        assert client.post(
            f"/history/{assessment_id}/archive",
            data={"csrf_token": csrf, "archived": "1"},
        ).status_code == 404
        csrf = _csrf(client, "/history")
        assert client.post(
            f"/history/{assessment_id}/delete",
            data={"csrf_token": csrf},
        ).status_code == 404
        csrf = _csrf(client, "/history")
        assert client.post(
            f"/feedback/{assessment_id}",
            data={"csrf_token": csrf, "helpful": "1"},
        ).status_code == 404
    finally:
        database.delete_user_account(other_id)


def test_account_export_is_owner_only_and_progress_supports_guest_history(client, user):
    user_id, email = user
    assert client.get("/history/progress").status_code == 200
    assert _login(client, email).status_code == 302
    with client.session_transaction() as state:
        sid = state["session_id"]
    _assessment(sid, user_id=user_id)
    response = client.get("/account/export")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["email"] == email
    assert all(record["id"] for record in payload["assessments"])
    assert client.get("/history/progress").status_code == 200


def test_password_reset_is_single_use_and_hashed(client, user):
    user_id, email = user
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    database.create_password_reset_token(
        user_id,
        token_hash,
        (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat(timespec="seconds"),
    )
    assert client.get(f"/reset-password/{raw_token}").status_code == 200
    response = client.post(
        f"/reset-password/{raw_token}",
        data={
            "csrf_token": _csrf(client, f"/reset-password/{raw_token}"),
            "password": "ResetStrong9!",
            "confirm_password": "ResetStrong9!",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert database.get_valid_password_reset_token(token_hash) is None
    assert token_hash != raw_token
    assert check_password_hash(database.get_user_by_id(user_id)["password_hash"], "ResetStrong9!")


def test_admin_routes_and_last_admin_protection(client, admin, user):
    admin_id, admin_email = admin
    user_id, user_email = user
    assert client.get("/admin").status_code == 302
    assert _login(client, user_email).status_code == 302
    assert client.get("/admin").status_code == 403
    client.post("/logout", data={"csrf_token": _csrf(client, "/history")})
    response = _login(client, admin_email)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")
    client.post("/logout", data={"csrf_token": _csrf(client, "/admin")})
    response = _login(client, admin_email, next_url="/assessment")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")
    for path in ("/admin", "/admin/users", "/admin/feedback", "/admin/audit", "/admin/system", "/admin/export.csv"):
        assert client.get(path).status_code == 200
    for path in ("/", "/assessment", "/history", "/history/progress", "/about", "/report"):
        response = client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/admin")
    response = client.post("/predict", data={"csrf_token": _csrf(client, "/admin")})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")
    account_page = client.get("/account").get_data(as_text=True)
    assert "Account" in account_page
    assert 'href="/admin"' in account_page
    assert 'href="/assessment"' not in account_page
    assert 'href="/history"' not in account_page
    dashboard = client.get("/admin").get_data(as_text=True)
    assert "Admin workspace" in dashboard
    assert "Individual health checks are not shown here" in dashboard
    assert 'href="/assessment"' not in dashboard
    assert 'href="/history"' not in dashboard
    # More tools links appear exactly once in the dashboard HTML (More tools card only, not nav/footer)
    assert dashboard.count('href="/admin/export.csv"') == 1
    assert dashboard.count('href="/admin/audit"') == 1
    assert dashboard.count('href="/admin/system"') == 1
    assert "Admin account menu for Test Admin" in dashboard
    assert "Sign out" in dashboard
    assert 'class="admin-account-menu"' in dashboard
    assert "<progress" in dashboard
    assert 'style="width:' not in dashboard
    csrf = _csrf(client, "/admin/users")
    assert client.post(
        f"/admin/users/{admin_id}/deactivate",
        data={"csrf_token": csrf},
    ).status_code == 403
    csrf = _csrf(client, "/admin/users")
    assert client.post(
        f"/admin/users/{user_id}/deactivate",
        data={"csrf_token": csrf},
    ).status_code == 302


def test_status_helper_and_csrf():
    assert app.get_status_presentation("Low")["label"] == "Good"
    assert app.get_status_presentation("Moderate")["label"] == "Check"
    assert app.get_status_presentation("High")["label"] == "See a doctor"
    assert app._admin_count(4) == "<5"
    assert app._admin_count(5) == "5"


def test_admin_small_cell_and_secondary_suppression(client, admin):
    _, admin_email = admin
    assert _login(client, admin_email).status_code == 302

    conn = database.get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO assessments (session_id, created_at, rule_matrix_version, bmi, age_band, gen_hlth, sex)
               VALUES ('test-suppression-sid', datetime('now'), '1.0', 22.0, 1, 1, 1)"""
        )
        asmt_id = cur.lastrowid

        # Domain 1 (Heart / cardiovascular): all 3 statuses >= 5 (all displayed)
        for _ in range(5):
            conn.execute("INSERT INTO risk_results (assessment_id, category, rule_label) VALUES (?, 'cardiovascular', 'Low')", (asmt_id,))
        for _ in range(6):
            conn.execute("INSERT INTO risk_results (assessment_id, category, rule_label) VALUES (?, 'cardiovascular', 'Moderate')", (asmt_id,))
        for _ in range(7):
            conn.execute("INSERT INTO risk_results (assessment_id, category, rule_label) VALUES (?, 'cardiovascular', 'High')", (asmt_id,))

        # Domain 2 (Kidneys / general_burden): one status = 4 (<5), others >= 5 -> all 3 show "<5"
        for _ in range(4):
            conn.execute("INSERT INTO risk_results (assessment_id, category, rule_label) VALUES (?, 'general_burden', 'Low')", (asmt_id,))
        for _ in range(5):
            conn.execute("INSERT INTO risk_results (assessment_id, category, rule_label) VALUES (?, 'general_burden', 'Moderate')", (asmt_id,))
        for _ in range(5):
            conn.execute("INSERT INTO risk_results (assessment_id, category, rule_label) VALUES (?, 'general_burden', 'High')", (asmt_id,))

        # Seeded feedback case 1: 4 yes / 6 no -> both "<5"
        for _ in range(4):
            conn.execute("INSERT INTO feedback (assessment_id, helpful, comment, created_at) VALUES (?, 1, 'yes', datetime('now'))", (asmt_id,))
        for _ in range(6):
            conn.execute("INSERT INTO feedback (assessment_id, helpful, comment, created_at) VALUES (?, 0, 'no', datetime('now'))", (asmt_id,))
        conn.commit()
    finally:
        conn.close()

    # Feedback tally: 4 yes / 6 no -> both suppressed (<5)
    tally_suppressed = app._admin_feedback_tally()
    assert tally_suppressed["yes"] == "<5"
    assert tally_suppressed["no"] == "<5"
    assert tally_suppressed["text"] == "Helpful: <5 yes / <5 no"

    # Seeded feedback case 2: add 2 yes (now 6 yes / 6 no) -> both shown
    conn = database.get_connection()
    try:
        for _ in range(2):
            conn.execute("INSERT INTO feedback (assessment_id, helpful, comment, created_at) VALUES (?, 1, 'yes', datetime('now'))", (asmt_id,))
        conn.commit()
    finally:
        conn.close()

    tally_shown = app._admin_feedback_tally()
    assert tally_shown["yes"] == "6"
    assert tally_shown["no"] == "6"
    assert tally_shown["text"] == "Helpful: 6 yes / 6 no"

    # Assert both domain status cases on /admin HTML
    dash_resp = client.get("/admin")
    assert dash_resp.status_code == 200
    dash_html = dash_resp.get_data(as_text=True)
    # Heart: all three statuses displayed
    assert ">5</strong>" in dash_html
    assert ">6</strong>" in dash_html
    assert ">7</strong>" in dash_html
    # Kidneys: one status is 4 (<5), so all three are suppressed to "<5"
    dash_data = app._admin_dashboard_data()
    assert dash_data["status_counts"]["Heart"] == {"Good": "5", "Check": "6", "See a doctor": "7"}
    assert dash_data["status_counts"]["Kidneys"] == {"Good": "<5", "Check": "<5", "See a doctor": "<5"}

    # Assert both domain status cases on /admin/export.csv
    csv_resp = client.get("/admin/export.csv")
    assert csv_resp.status_code == 200
    csv_text = csv_resp.get_data(as_text=True)
    assert "generated_at," in csv_text
    assert "suppression_note,Counts below 5 are shown as <5" in csv_text
    assert "heart_good,5" in csv_text
    assert "heart_check,6" in csv_text
    assert "heart_see_a_doctor,7" in csv_text
    assert "kidneys_good,<5" in csv_text
    assert "kidneys_check,<5" in csv_text
    assert "kidneys_see_a_doctor,<5" in csv_text

    # Cell starting with = should be neutralized
    assert app._sanitize_csv_cell("=SUM(1,2)") == "'=SUM(1,2)"
    assert app._sanitize_csv_cell("+100") == "'+100"
    assert app._sanitize_csv_cell("@alert") == "'@alert"


def test_admin_feedback_submissions_render_not_rated(client, admin):
    _, admin_email = admin
    unique_msg = f"Feedback-Test-{uuid.uuid4().hex}"
    database.save_feedback_submission("Test Patient", unique_msg)

    assert _login(client, admin_email).status_code == 302
    resp = client.get("/admin/feedback")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert unique_msg in html
    assert "Not rated" in html
    assert "Helpful:" in html


def test_admin_actions_confirmation_and_button_visibility(client, admin, user):
    admin_id, admin_email = admin
    user_id, user_email = user
    assert _login(client, admin_email).status_code == 302

    # Verify users table with single active admin
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # For admin self: Deactivate form must NOT render
    assert f'action="/admin/users/{admin_id}/deactivate"' not in html
    # For admin self (as last active admin): Delete must NOT render, note must render
    assert f'action="/admin/users/{admin_id}/delete"' not in html
    assert "Last active admin" in html

    # Data confirm message checks
    assert 'data-confirm-message="Create a 60-minute password reset link for this user?"' in html
    # Deactivate other user first to check reactivate form
    csrf = _csrf(client, "/admin/users")
    client.post(f"/admin/users/{user_id}/deactivate", data={"csrf_token": csrf})
    resp_inactive = client.get("/admin/users")
    html_inactive = resp_inactive.get_data(as_text=True)
    assert f'action="/admin/users/{user_id}/reactivate"' in html_inactive
    assert 'data-confirm-message="Reactivate this user?"' in html_inactive

    # Create backup confirmation on system page
    sys_resp = client.get("/admin/system")
    assert sys_resp.status_code == 200
    sys_html = sys_resp.get_data(as_text=True)
    assert 'data-confirm-message="Create a new encrypted database backup?"' in sys_html


def test_admin_audit_pagination_and_filter(client, admin):
    admin_id, admin_email = admin
    assert _login(client, admin_email).status_code == 302

    conn = database.get_connection()
    try:
        for _ in range(60):
            conn.execute(
                """INSERT INTO audit_log (actor_user_id, action, target, ip, created_at)
                   VALUES (?, 'admin_backup_created', NULL, '127.0.0.1', datetime('now'))""",
                (admin_id,),
            )
        conn.commit()
    finally:
        conn.close()

    # Page 1: has Next, no Previous, link keeps action=admin_backup_created
    resp_p1 = client.get("/admin/audit?action=admin_backup_created")
    assert resp_p1.status_code == 200
    html_p1 = resp_p1.get_data(as_text=True)
    assert "admin_backup_created" in html_p1
    assert '<select id="auditAction" name="action"' in html_p1
    assert 'value="admin_backup_created" selected' in html_p1
    assert "Next page" in html_p1
    assert "Previous page" not in html_p1
    assert "action=admin_backup_created" in html_p1

    # Page 2: has Previous, no Next, link keeps action=admin_backup_created
    resp_p2 = client.get("/admin/audit?page=2&action=admin_backup_created")
    assert resp_p2.status_code == 200
    html_p2 = resp_p2.get_data(as_text=True)
    assert "Previous page" in html_p2
    assert "Next page" not in html_p2
    assert "action=admin_backup_created" in html_p2


def test_admin_system_page_metrics_and_chips(client, admin):
    _, admin_email = admin
    assert _login(client, admin_email).status_code == 302

    resp = client.get("/admin/system")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "Database status" in html
    assert "Connected" in html
    assert "4 of 4 loaded" in html
    assert "Running for" in html
    assert ("MB" in html or "KB" in html or "bytes" in html)
    assert "Guest checks are deleted after 90 days. Accounts are kept until deleted." in html
    assert "Loaded" in html
    # Model titles from shared mapping
    assert "Heart" in html
    assert "Kidneys" in html
    assert "Nerves and feet" in html
    assert "Eyes" in html


def test_admin_never_exposes_individual_health_data(client, admin):
    _, admin_email = admin
    unique_bmi = 77.3
    unique_hba1c = 14.89
    lab_assessment = compute_lab_assessment(hba1c=unique_hba1c)
    sid = f"privacy-test-{uuid.uuid4().hex}"
    results = {
        category: {"score": 2, "percentage": 85, "label": "High"}
        for category in ("cardiovascular", "general_burden", "neuropathy_mobility", "retinopathy")
    }
    assessment_id = database.save_assessment(
        sid,
        {"BMI": unique_bmi, "Age": 5, "GenHlth": 4, "Sex": 1},
        results,
        model_results={},
        lab_assessment=lab_assessment,
    )

    conn = database.get_connection()
    try:
        lab_row_count = conn.execute(
            "SELECT COUNT(*) FROM lab_assessments WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchone()[0]
        assert lab_row_count == 1, "Lab assessment row was not inserted"
    finally:
        conn.close()

    assert _login(client, admin_email).status_code == 302

    admin_endpoints = [
        "/admin",
        "/admin/users",
        "/admin/feedback",
        "/admin/audit",
        "/admin/system",
        "/admin/export.csv",
    ]
    for endpoint in admin_endpoints:
        res = client.get(endpoint)
        assert res.status_code == 200
        body = res.get_data(as_text=True)
        assert str(unique_bmi) not in body, f"Leaked BMI on {endpoint}"
        assert str(unique_hba1c) not in body, f"Leaked HbA1c on {endpoint}"
        assert "77.3" not in body
        assert "14.89" not in body
        assert "no-store" in res.headers.get("Cache-Control", ""), f"Missing no-store on {endpoint}"


def test_admin_route_authorization_boundaries(client, user):
    _, user_email = user
    admin_endpoints = [
        "/admin",
        "/admin/users",
        "/admin/feedback",
        "/admin/audit",
        "/admin/system",
        "/admin/export.csv",
    ]

    for endpoint in admin_endpoints:
        res = client.get(endpoint)
        assert res.status_code == 302, f"Anonymous should redirect on {endpoint}"
        assert "/login" in res.headers["Location"]

    assert _login(client, user_email).status_code == 302
    for endpoint in admin_endpoints:
        res = client.get(endpoint)
        assert res.status_code == 403, f"Non-admin should get 403 on {endpoint}"
