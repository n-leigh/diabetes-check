import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import check_password_hash

import app
import database


PASSWORD = "StrongTestPass9!"


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


def test_account_export_is_owner_only_and_progress_is_authenticated(client, user):
    user_id, email = user
    assert client.get("/history/progress").status_code == 302
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
    assert _login(client, admin_email).status_code == 302
    for path in ("/admin", "/admin/users", "/admin/feedback", "/admin/audit", "/admin/system", "/admin/export.csv"):
        assert client.get(path).status_code == 200
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
