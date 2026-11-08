import hashlib
import os
import re
import tempfile

os.environ["DB_BACKEND"] = "sqlite"
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "true"
os.environ["SMTP_HOST"] = "smtp.test"
os.environ["SMTP_PORT"] = "587"
os.environ["SMTP_USER"] = "test-user"
os.environ["SMTP_PASSWORD"] = "test-password"
os.environ["SMTP_FROM"] = "DiaBeates <test@example.test>"
os.environ["BASE_URL"] = "http://localhost:5000"

import pytest

import database

_TEMP_DIR = tempfile.TemporaryDirectory()
database.DB_PATH = os.path.join(_TEMP_DIR.name, "test.db")
database.KEY_PATH = os.path.join(_TEMP_DIR.name, "key")
database.PROTECTED_KEY_PATH = os.path.join(_TEMP_DIR.name, "key.dpapi")

import app


def _csrf(client, path):
    body = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', body).group(1)


@pytest.fixture
def client(monkeypatch):
    sent = []
    monkeypatch.setattr(app, "_send_verification_email", lambda email, name, link: sent.append(link) or True)
    test_client = app.app.test_client()
    test_client.sent_verification_links = sent
    return test_client


def _register(client, email, nickname="Test User"):
    return client.post(
        "/register",
        data={
            "csrf_token": _csrf(client, "/register"),
            "nickname": nickname,
            "email": email,
            "password": "StrongTestPass9!",
            "confirm_password": "StrongTestPass9!",
            "consent": "1",
        },
        follow_redirects=False,
    )


def test_registration_stores_only_hash_and_get_does_not_consume(client):
    response = _register(client, "verify@example.test")
    assert response.status_code == 302
    row = database.get_user_by_email("verify@example.test")
    assert row["email_verified_at"] is None
    raw_token = client.sent_verification_links[0].rsplit("/", 1)[-1]
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    stored = database.get_connection().execute(
        "SELECT token_hash FROM email_verification_tokens WHERE user_id = ?", (row["id"],)
    ).fetchone()["token_hash"]
    assert stored == token_hash
    assert raw_token not in stored
    path = f"/verify-email/{raw_token}"
    assert client.get(path).status_code == 200
    assert database.get_email_verification_token(token_hash)


def test_post_verification_is_single_use_and_allows_login(client):
    _register(client, "single@example.test")
    path = f"/verify-email/{client.sent_verification_links[0].rsplit('/', 1)[-1]}"
    assert client.post(path, data={"csrf_token": _csrf(client, path)}).status_code == 200
    assert client.post(path, data={"csrf_token": _csrf(client, "/login")}).status_code == 200
    assert "needs replacing" in client.get(path).get_data(as_text=True)
    response = client.post(
        "/login",
        data={"csrf_token": _csrf(client, "/login"), "email": "single@example.test", "password": "StrongTestPass9!"},
    )
    assert response.status_code == 302


def test_unverified_reregistration_replaces_token_and_blocks_login(client):
    _register(client, "pending@example.test", "First")
    first_link = client.sent_verification_links[-1]
    response = client.post(
        "/login",
        data={"csrf_token": _csrf(client, "/login"), "email": "pending@example.test", "password": "StrongTestPass9!"},
    )
    assert "Please confirm your email first." in response.get_data(as_text=True)
    _register(client, "pending@example.test", "Updated")
    assert client.sent_verification_links[-1] != first_link
    count = database.get_connection().execute(
        "SELECT count(*) FROM email_verification_tokens WHERE user_id = ?",
        (database.get_user_by_email("pending@example.test")["id"],),
    ).fetchone()[0]
    assert count == 1


def test_password_reset_marks_email_verified():
    user_id = database.create_user("reset@example.test", "StrongTestPass9!", "Reset", email_verified_at=None)
    raw_token = "reset-token"
    database.create_password_reset_token(
        user_id,
        hashlib.sha256(raw_token.encode()).hexdigest(),
        "2999-01-01T00:00:00+00:00",
    )
    database.complete_password_reset(
        database.get_valid_password_reset_token(hashlib.sha256(raw_token.encode()).hexdigest())["id"],
        user_id,
        "NewStrongPass9!",
    )
    database.mark_email_verified(user_id)
    assert database.get_user_by_id(user_id)["email_verified_at"] is not None
