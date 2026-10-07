"""
app.py — Web-Based Diabetes Complication Prediction System

Combines:
1. Dual-Engine Clinical Architecture:
   - Transparent, evidence-based clinical rule matrix (Version 2.0-clinical: ACC/AHA, KDIGO 2024, MNSI)
   - Calibrated machine learning models trained on authentic CDC NHANES diabetic cohorts
2. Production Hardening & Reliability:
   - CSRF protection on all POST forms via Flask-WTF
   - Rate limiting via Flask-Limiter
   - Environment secret configuration (.env)
   - Rotating file application logger (logs/diabetes_system.log)
   - Safe, non-destructive SQLite database migrations with WAL mode

Run: python3 app.py
Then open http://127.0.0.1:5000
"""

import os
import json
import hashlib
import smtplib
import csv
import io
import shutil
import uuid
import secrets
import logging
import logging.handlers
import re
import sqlite3
import threading
import zipfile
from functools import wraps
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import joblib
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
import click

import clinical_model
from rule_matrix import compute_all_risks, compute_lab_assessment, RULE_VERSION
from recommendations import build_recommendations
from validation import validate_patient_form
from field_labels import describe_patient
import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ===== LOGGING CONFIGURATION =====
log_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "diabetes_system.log"),
            maxBytes=10485760,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DiaBeates")

secret_key_path = os.path.join(BASE_DIR, ".secret_key")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    try:
        # Create a persisted key if missing/empty.
        if not os.path.exists(secret_key_path) or os.path.getsize(secret_key_path) == 0:
            with open(secret_key_path, "w", encoding="utf-8") as secret_file:
                secret_file.write(secrets.token_hex(32))
            # Best-effort permission hardening on POSIX.
            try:
                os.chmod(secret_key_path, 0o600)
            except OSError:
                pass

        with open(secret_key_path, encoding="utf-8") as secret_file:
            SECRET_KEY = secret_file.read().strip()
    except OSError:
        # Read-only FS / permission error: fall back to a non-persisted key.
        SECRET_KEY = secrets.token_hex(32)

if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
DEBUG = os.getenv("DEBUG", "False").strip().lower() in {"1", "true", "yes", "on"}
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "False").strip().lower() in {"1", "true", "yes", "on"}
DISPLAY_TIMEZONE = os.getenv("DISPLAY_TIMEZONE", "Asia/Manila").strip() or "Asia/Manila"
try:
    DISPLAY_ZONE = ZoneInfo(DISPLAY_TIMEZONE)
except Exception:
    logger.warning("Invalid DISPLAY_TIMEZONE '%s'; falling back to Asia/Manila.", DISPLAY_TIMEZONE)
    DISPLAY_TIMEZONE = "Asia/Manila"
    DISPLAY_ZONE = ZoneInfo(DISPLAY_TIMEZONE)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    WTF_CSRF_TIME_LIMIT=None,
    TEMPLATES_AUTO_RELOAD=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    REMEMBER_COOKIE_SECURE=COOKIE_SECURE,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE="Lax",
    REMEMBER_COOKIE_DURATION=timedelta(days=7),
    PERMANENT_SESSION_LIFETIME=timedelta(days=90),
)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.session_protection = "basic"
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to view that page."


class AuthUser(UserMixin):
    def __init__(self, row):
        self.id = int(row["id"])
        self.email = row["email"]
        self.display_name = row["display_name"]
        self.role = row["role"]
        self.is_active = bool(row["is_active"])

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = bool(value)


@login_manager.user_loader
def load_user(user_id):
    try:
        row = database.get_user_by_id(int(user_id))
    except (TypeError, ValueError):
        return None
    return AuthUser(row) if row else None


_DUMMY_PASSWORD_HASH = generate_password_hash("dummy-password-for-timing", method="scrypt")
COMMON_PASSWORDS = {
    "123456", "123456789", "12345", "password", "password1", "12345678",
    "qwerty", "abc123", "111111", "123123", "admin", "letmein",
    "welcome", "monkey", "dragon", "football", "iloveyou", "sunshine",
    "princess", "master", "login", "passw0rd", "qwerty123", "password123",
}

STATUS_PRESENTATIONS = {
    "Low": {
        "label": "Good",
        "icon": "✓",
        "text_class": "text-[#2f7d4a]",
        "background_class": "bg-[#e4f2e7]",
        "border_class": "border-[#bce0c6]",
    },
    "Moderate": {
        "label": "Check",
        "icon": "!",
        "text_class": "text-[#a86a0a]",
        "background_class": "bg-[#fbeed0]",
        "border_class": "border-[#f4d99f]",
    },
    "High": {
        "label": "See a doctor",
        "icon": "!",
        "text_class": "text-[#b03a2e]",
        "background_class": "bg-[#f9e1dc]",
        "border_class": "border-[#f1b8af]",
    },
}


def get_status_presentation(rule_label):
    return STATUS_PRESENTATIONS.get(rule_label, STATUS_PRESENTATIONS["High"]).copy()


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin" or not current_user.is_active:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _admin_count(value, total):
    return str(value) if total >= 5 else "<5"


def _admin_dashboard_data():
    conn = database.get_connection()
    try:
        now = datetime.now(timezone.utc)
        users_total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= ?",
            ((now - timedelta(days=7)).isoformat(timespec="seconds"),),
        ).fetchone()[0]
        assessments_total = conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]
        feedback_total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        helpful_total = conn.execute("SELECT COUNT(*) FROM feedback WHERE helpful = 1").fetchone()[0]
        status_counts = {}
        for category, title in (
            ("cardiovascular", "Heart"),
            ("general_burden", "Kidneys"),
            ("neuropathy_mobility", "Nerves and feet"),
            ("retinopathy", "Eyes"),
        ):
            rows = conn.execute(
                """SELECT rule_label, COUNT(*) AS total FROM risk_results
                   WHERE category = ? GROUP BY rule_label""",
                (category,),
            ).fetchall()
            total = sum(row["total"] for row in rows)
            status_counts[title] = {
                get_status_presentation(row["rule_label"])["label"]: _admin_count(row["total"], total)
                for row in rows
            }
        days = []
        for offset in range(29, -1, -1):
            day = (now - timedelta(days=offset)).date()
            count = conn.execute(
                "SELECT COUNT(*) FROM assessments WHERE date(created_at) = ?",
                (day.isoformat(),),
            ).fetchone()[0]
            days.append({"date": day.isoformat(), "count": count})
        return {
            "users_total": users_total,
            "new_users": _admin_count(new_users, users_total),
            "assessments_total": assessments_total,
            "feedback_helpful": _admin_count(helpful_total, feedback_total),
            "status_counts": status_counts,
            "days": days,
        }
    finally:
        conn.close()


def _safe_next_url(value):
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return url_for("history")


def _password_error(password, email):
    normalized = (password or "").strip().lower()
    return (
        len(password or "") < 8
        or len(password or "") > 128
        or normalized in COMMON_PASSWORDS
        or normalized == (email or "").strip().lower()
    )

# ===== IN-MEMORY ASSESSMENT STORE =====
# Single-process deployment constraint:
# This in-process memory model assumes single-process multi-threaded deployment 
# (Waitress on 127.0.0.1:5000 with 8 worker threads per wsgi.py). 
# Scaling to multiple worker processes requires a shared server-side store (e.g. Redis).
_IN_MEMORY_ASSESSMENTS = {}
_IN_MEMORY_LOCK = threading.Lock()
IN_MEMORY_TTL_SECONDS = 900  # 15 minutes
PRINT_TOKEN_TTL_SECONDS = 300 # 5 minutes
MAX_IN_MEMORY_ITEMS = 500

def _prune_in_memory_assessments():
    """Purge expired assessments and enforce LRU eviction limit."""
    now = datetime.now(timezone.utc).timestamp()
    with _IN_MEMORY_LOCK:
        # Step 1: Purge expired
        expired = [
            sid for sid, data in _IN_MEMORY_ASSESSMENTS.items() 
            if (now - data['timestamp']) > (PRINT_TOKEN_TTL_SECONDS if data.get("is_print_token") else IN_MEMORY_TTL_SECONDS)
        ]
        for sid in expired:
            del _IN_MEMORY_ASSESSMENTS[sid]
        
        # Step 2: LRU eviction if over capacity
        if len(_IN_MEMORY_ASSESSMENTS) >= MAX_IN_MEMORY_ITEMS:
            # Sort by timestamp ascending (oldest first)
            sorted_items = sorted(_IN_MEMORY_ASSESSMENTS.items(), key=lambda item: item[1]['timestamp'])
            # Remove oldest items until we are below capacity (e.g., 499 to allow 1 new write)
            while len(_IN_MEMORY_ASSESSMENTS) >= MAX_IN_MEMORY_ITEMS:
                oldest_sid = sorted_items.pop(0)[0]
                if oldest_sid in _IN_MEMORY_ASSESSMENTS:
                    del _IN_MEMORY_ASSESSMENTS[oldest_sid]


@app.template_filter("display_time")
def display_time(value):
    if not value:
        return ""
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(DISPLAY_ZONE).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return value

@app.after_request
def set_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    if not DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Enforce strict Cache-Control for sensitive clinical routes
    if request.path == "/predict" or request.path.startswith("/print") or request.path.startswith("/history") or request.path.startswith("/result"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    return response


limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["300 per day", "100 per hour"],
    storage_uri="memory://",
)

database.init_db()
database.verify_database_integrity()
logger.info("Database initialized successfully with non-destructive WAL mode.")
try:
    RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))
except ValueError:
    logger.warning("Invalid RETENTION_DAYS; falling back to 90.")
    RETENTION_DAYS = 90

if RETENTION_DAYS < 1:
    logger.warning("RETENTION_DAYS must be >= 1; falling back to 90.")
    RETENTION_DAYS = 90

try:
    pruned_count = database.prune_expired_assessments(days=RETENTION_DAYS)
except Exception:
    logger.exception("Failed to prune expired assessments")
    pruned_count = 0

if pruned_count:
    logger.info("Expired assessments pruned: %d", pruned_count)

CATEGORIES = ["cardiovascular", "neuropathy_mobility", "general_burden", "retinopathy"]
FEATURE_COLUMNS = [
    "HighBP", "HighChol", "Smoker", "HeartDiseaseorAttack", "Stroke",
    "BMI", "Age", "DiffWalk", "PhysHlth", "GenHlth", "MentHlth",
    "NoDocbcCost", "Sex", "DiabetesDuration", "BlurryVision",
]

# ===== MODEL LOADING WITH ERROR HANDLING =====
MODELS = {}
MODEL_NAMES = {}
CLINICAL_METRICS = {}
_summary_path = os.path.join(BASE_DIR, "model", "training_summary.json")
if os.path.exists(_summary_path):
    try:
        with open(_summary_path) as f:
            _summary = json.load(f)
            MODEL_NAMES = {cat: _summary[cat]["best_model"] for cat in _summary}
            CLINICAL_METRICS = _summary
        logger.info(f"Loaded clinical models summary: {list(MODEL_NAMES.keys())}")
    except Exception as e:
        logger.error(f"Failed to load training_summary.json: {e}")

for cat in CATEGORIES:
    path = os.path.join(BASE_DIR, "model", f"{cat}_model.pkl")
    if os.path.exists(path):
        try:
            model = joblib.load(path)
            if hasattr(model, "classes_") and not np.array_equal(np.asarray(model.classes_), np.array([0, 1])):
                raise ValueError("model classes_ must be [0, 1]")
            MODELS[cat] = model
        except Exception as e:
            logger.error(f"Error loading model for {cat}: {e}")
    else:
        logger.warning(f"Model file not found for '{cat}' at {path}")


def _send_reset_email(email, reset_link):
        smtp_host = os.getenv("SMTP_HOST", "").strip()
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        smtp_from = os.getenv("SMTP_FROM", "").strip()
        if not smtp_host or not smtp_from:
            if DEBUG:
                logger.info("Password reset link for configured debug delivery: %s", reset_link)
                return True
            return False
        message = EmailMessage()
        message["Subject"] = "DiaBeates password reset"
        message["From"] = smtp_from
        message["To"] = email
        message.set_content(f"Use this link within 60 minutes to reset your password:\n\n{reset_link}")
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        return True


def _reset_link(token):
        base_url = os.getenv("BASE_URL", "").strip().rstrip("/")
        if base_url:
            return f"{base_url}{url_for('reset_password', token=token)}"
        return url_for("reset_password", token=token, _external=True)


def _post_auth_redirect(next_url=None):
        claim_sid = session.get("claim_sid")
        if claim_sid and database.get_unclaimed_assessments(claim_sid):
            return redirect(url_for("claim"))
        return redirect(_safe_next_url(next_url))


@app.before_request
def ensure_session_id():
    if current_user.is_authenticated and current_user.role == "admin":
        last_seen = session.get("admin_last_seen")
        now = datetime.now(timezone.utc).timestamp()
        if last_seen and now - last_seen > 1800:
            logout_user()
            session.pop("admin_last_seen", None)
            return redirect(url_for("login", next=request.full_path))
        session["admin_last_seen"] = now
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session.permanent = True


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("history"))
    errors = []
    if request.method == "POST":
        display_name = request.form.get("nickname", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        consent = request.form.get("consent") == "1"
        if not display_name or len(display_name) > 40:
            errors.append("Enter a nickname from 1 to 40 characters.")
        if not email or len(email) > 254 or "@" not in email:
            errors.append("Enter a valid email address.")
        if _password_error(password, email):
            errors.append("Use a password with 8 to 128 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if not consent:
            errors.append("Please agree to the Privacy Notice.")
        if not errors:
            try:
                user_id = database.create_user(email, password, display_name)
            except sqlite3.IntegrityError:
                errors.append("That email is already registered.")
            else:
                guest_sid = session.get("session_id")
                session.clear()
                session["session_id"] = str(uuid.uuid4())
                session.permanent = True
                if guest_sid:
                    session["claim_sid"] = guest_sid
                user = load_user(user_id)
                login_user(user, remember=False)
                database.log_audit("login_success", str(user_id), user_id, get_remote_address())
                return _post_auth_redirect(request.args.get("next"))
    return render_template("register.html", errors=errors, form_data=request.form)


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("history"))
    errors = []
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "1"
        row = database.get_user_by_email(email)
        password_matches = check_password_hash(row["password_hash"], password) if row else check_password_hash(
            _DUMMY_PASSWORD_HASH, password
        )
        now = datetime.now(timezone.utc)
        locked = False
        if row and row["locked_until"]:
            try:
                locked = datetime.fromisoformat(row["locked_until"]).replace(tzinfo=timezone.utc) > now
            except ValueError:
                locked = False
        if row and locked:
            errors.append("Too many tries. Please wait 15 minutes and try again.")
        elif not row or not row["is_active"] or not password_matches:
            if row and row["is_active"]:
                failed_attempts = int(row["failed_attempts"]) + 1
                lock_until = (now + timedelta(minutes=15)).isoformat(timespec="seconds") if failed_attempts >= 5 else None
                database.set_lock(row["id"], failed_attempts, lock_until)
                database.log_audit("lockout" if lock_until else "login_failed", str(row["id"]), None, get_remote_address())
            elif row:
                database.log_audit("login_failed", str(row["id"]), None, get_remote_address())
            errors.append("Email or password is incorrect.")
        else:
            guest_sid = session.get("session_id")
            session.clear()
            session["session_id"] = str(uuid.uuid4())
            session.permanent = True
            if guest_sid:
                session["claim_sid"] = guest_sid
            database.record_login_success(row["id"])
            user = AuthUser(row)
            login_user(user, remember=remember and user.role != "admin")
            database.log_audit("login_success", str(user.id), user.id, get_remote_address())
            return _post_auth_redirect(request.args.get("next"))
    return render_template("login.html", errors=errors, form_data=request.form)


@app.post("/logout")
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    session.clear()
    database.log_audit("logout", str(user_id), user_id, get_remote_address())
    return redirect(url_for("index"))


@app.route("/privacy", methods=["GET"])
def privacy():
    return render_template("privacy.html")


@app.route("/account", methods=["GET"])
@login_required
def account():
    return render_template("account.html", user=database.get_user_by_id(current_user.id), message=request.args.get("message"))


@app.post("/account/profile")
@login_required
def account_profile():
    display_name = request.form.get("nickname", "").strip()
    if not display_name or len(display_name) > 40:
        return redirect(url_for("account", message="Enter a nickname from 1 to 40 characters."))
    conn = database.get_connection()
    try:
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, current_user.id))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("account", message="Your details were saved."))


@app.post("/account/password")
@login_required
def account_password():
    row = database.get_user_by_id(current_user.id)
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    if not check_password_hash(row["password_hash"], current_password):
        message = "Your current password is incorrect."
    elif _password_error(new_password, row["email"]):
        message = "Use a password with 8 to 128 characters."
    elif new_password != confirm_password:
        message = "Passwords do not match."
    else:
        database.update_password(current_user.id, new_password)
        database.log_audit("password_changed", str(current_user.id), current_user.id, get_remote_address())
        message = "Your password was changed."
    return redirect(url_for("account", message=message))


@app.post("/account/delete")
@login_required
def account_delete():
    row = database.get_user_by_id(current_user.id)
    if not check_password_hash(row["password_hash"], request.form.get("current_password", "")):
        return redirect(url_for("account", message="Your current password is incorrect."))
    user_id = current_user.id
    database.log_audit("account_deleted", str(user_id), user_id, get_remote_address())
    database.delete_user_account(user_id)
    logout_user()
    session.clear()
    return redirect(url_for("index", deleted="1"))


@app.get("/account/export")
@login_required
def account_export():
    records = database.get_all_assessments(
        session_id=session["session_id"], user_id=current_user.id, limit=10000, sort_order="asc"
    )
    payload = {
        "nickname": current_user.display_name,
        "email": current_user.email,
        "assessments": records,
    }
    response = app.response_class(
        json.dumps(payload, default=str, ensure_ascii=False),
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = "attachment; filename=diabeates-data.json"
    return response


@app.get("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", dashboard=_admin_dashboard_data())


@app.get("/admin/users")
@admin_required
def admin_users():
    conn = database.get_connection()
    try:
        users = [dict(row) for row in conn.execute(
            """SELECT id, display_name, email, role, is_active, created_at, last_login_at
               FROM users ORDER BY id DESC"""
        ).fetchall()]
    finally:
        conn.close()
    reset_link = session.pop("admin_reset_link", None)
    return render_template("admin_users.html", users=users, reset_link=reset_link)


def _active_admin_count():
    conn = database.get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
        ).fetchone()[0]
    finally:
        conn.close()


@app.post("/admin/users/<int:user_id>/deactivate")
@admin_required
def admin_deactivate_user(user_id):
    row = database.get_user_by_id(user_id)
    if not row or row["id"] == current_user.id or (
        row["role"] == "admin" and row["is_active"] and _active_admin_count() <= 1
    ):
        abort(403)
    conn = database.get_connection()
    try:
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    database.log_audit("admin_user_deactivated", str(user_id), current_user.id, get_remote_address())
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:user_id>/reactivate")
@admin_required
def admin_reactivate_user(user_id):
    row = database.get_user_by_id(user_id)
    if not row:
        abort(404)
    conn = database.get_connection()
    try:
        conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    database.log_audit("admin_user_reactivated", str(user_id), current_user.id, get_remote_address())
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:user_id>/delete")
@admin_required
def admin_delete_user(user_id):
    row = database.get_user_by_id(user_id)
    if not row or row["id"] == current_user.id or (
        row["role"] == "admin" and row["is_active"] and _active_admin_count() <= 1
    ):
        abort(403)
    database.log_audit("admin_user_deleted", str(user_id), current_user.id, get_remote_address())
    database.delete_user_account(user_id)
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:user_id>/reset-link")
@admin_required
def admin_reset_link(user_id):
    row = database.get_user_by_id(user_id)
    if not row:
        abort(404)
    raw_token = secrets.token_urlsafe(32)
    database.create_password_reset_token(
        user_id,
        hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat(timespec="seconds"),
    )
    session["admin_reset_link"] = _reset_link(raw_token)
    database.log_audit("admin_reset_link_created", str(user_id), current_user.id, get_remote_address())
    return redirect(url_for("admin_users"))


@app.get("/admin/feedback")
@admin_required
def admin_feedback():
    conn = database.get_connection()
    try:
        feedback = [dict(row) for row in conn.execute(
            "SELECT helpful, comment, created_at FROM feedback ORDER BY created_at DESC LIMIT 200"
        ).fetchall()]
    finally:
        conn.close()
    return render_template("admin_feedback.html", feedback=feedback)


@app.get("/admin/audit")
@admin_required
def admin_audit():
    page = max(1, request.args.get("page", 1, type=int))
    action = request.args.get("action", "").strip()
    offset = (page - 1) * 50
    conn = database.get_connection()
    try:
        where = "WHERE action = ?" if action else ""
        params = (action, 50, offset) if action else (50, offset)
        audit = [dict(row) for row in conn.execute(
            f"""SELECT id, actor_user_id, action, target, ip, created_at
                FROM audit_log {where} ORDER BY id DESC LIMIT ? OFFSET ?""",
            params,
        ).fetchall()]
    finally:
        conn.close()
    return render_template("admin_audit.html", audit=audit, action=action, page=page)


@app.get("/admin/system")
@admin_required
def admin_system():
    backups_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    backups = sorted(
        [name for name in os.listdir(backups_dir) if name.endswith(".zip")],
        reverse=True,
    )
    try:
        database_size = os.path.getsize(database.DB_PATH)
    except OSError:
        database_size = 0
    return render_template(
        "admin_system.html",
        backups=backups,
        database_size=database_size,
        model_names=MODEL_NAMES,
        retention_days=RETENTION_DAYS,
        backup_message=session.pop("backup_message", None),
    )


@app.post("/admin/system/backup")
@admin_required
def admin_backup():
    backups_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backups_dir, f"diabeates-backup-{stamp}.zip")
    database_hash = hashlib.sha256()
    with open(database.DB_PATH, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            database_hash.update(block)
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(database.DB_PATH, "diabetes_system.db")
        archive.writestr("SHA256SUM", f"{database_hash.hexdigest()}  diabetes_system.db\n")
    database.restrict_database_permissions(backup_path)
    database.log_audit("admin_backup_created", None, current_user.id, get_remote_address())
    session["backup_message"] = "Backup created."
    return redirect(url_for("admin_system"))


@app.get("/admin/export.csv")
@admin_required
def admin_export_csv():
    dashboard = _admin_dashboard_data()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    writer.writerow(["total_users", dashboard["users_total"]])
    writer.writerow(["new_users_last_7_days", dashboard["new_users"]])
    writer.writerow(["total_assessments", dashboard["assessments_total"]])
    writer.writerow(["feedback_helpful", dashboard["feedback_helpful"]])
    for title, counts in dashboard["status_counts"].items():
        for status, value in counts.items():
            writer.writerow([f"{title.lower()}_{status.lower().replace(' ', '_')}", value])
    response = app.response_class(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=diabeates-admin-summary.csv"
    return response


@app.get("/history/progress")
@login_required
def history_progress():
    records = database.get_all_assessments(
        session_id=session["session_id"],
        user_id=current_user.id,
        limit=200,
        sort_order="asc",
    )
    domains = [
        ("cardiovascular", "Heart"),
        ("general_burden", "Kidneys"),
        ("neuropathy_mobility", "Nerves and feet"),
        ("retinopathy", "Eyes"),
    ]
    progress = []
    for category, title in domains:
        entries = []
        for record in records:
            result = record["rule_results"].get(category)
            if result:
                entries.append({
                    "date": record["created_at"],
                    "status": get_status_presentation(result.get("label")),
                })
        progress.append({
            "category": category,
            "title": title,
            "entries": entries,
            "sentence": _progress_sentence(title, entries),
        })
    return render_template("progress.html", progress=progress, check_count=len(records))


def _progress_sentence(title, entries):
    if len(entries) < 2:
        return None
    first = entries[0]
    latest = entries[-1]
    first_date = datetime.fromisoformat(first["date"].replace("Z", "+00:00")).astimezone(DISPLAY_ZONE)
    latest_date = datetime.fromisoformat(latest["date"].replace("Z", "+00:00")).astimezone(DISPLAY_ZONE)
    return (
        f"{title}: {first['status']['label']} in {first_date.strftime('%B')}, "
        f"{latest['status']['label']} in {latest_date.strftime('%B')}."
    )


@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        row = database.get_user_by_email(email)
        delivery_configured = bool(os.getenv("SMTP_HOST", "").strip() and os.getenv("SMTP_FROM", "").strip())
        if row:
            raw_token = secrets.token_urlsafe(32)
            database.create_password_reset_token(
                row["id"],
                hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat(timespec="seconds"),
            )
            link = _reset_link(raw_token)
            try:
                sent = _send_reset_email(row["email"], link)
            except (OSError, smtplib.SMTPException, ValueError):
                logger.exception("Password reset email delivery failed")
                sent = False
            if not sent and not DEBUG:
                logger.info("Password reset fallback used for user id %s", row["id"])
            database.log_audit("password_reset_requested", str(row["id"]), None, get_remote_address())
        fallback_text = os.getenv(
            "ADMIN_CONTACT_TEXT",
            "Password reset by email is not set up. Please ask the site administrator to reset your password.",
        )
        return render_template(
            "forgot_password.html",
            submitted=True,
            fallback_text=fallback_text if not delivery_configured and not DEBUG else None,
        )
    return render_template("forgot_password.html", submitted=False)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_row = database.get_valid_password_reset_token(
        hashlib.sha256(token.encode("utf-8")).hexdigest()
    )
    errors = []
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not token_row:
            errors.append("This reset link is invalid or expired.")
        elif _password_error(password, database.get_user_by_id(token_row["user_id"])["email"]):
            errors.append("Use a password with 8 to 128 characters.")
        elif password != confirm_password:
            errors.append("Passwords do not match.")
        else:
            database.complete_password_reset(token_row["id"], token_row["user_id"], password)
            database.log_audit("password_reset_completed", str(token_row["user_id"]), token_row["user_id"], get_remote_address())
            return redirect(url_for("login"))
    return render_template("reset_password.html", errors=errors, invalid=token_row is None)


@app.route("/claim", methods=["GET", "POST"])
@login_required
def claim():
    claim_sid = session.get("claim_sid")
    if not claim_sid:
        return redirect(url_for("history"))
    checks = database.get_unclaimed_assessments(claim_sid)
    if not checks:
        session.pop("claim_sid", None)
        return redirect(url_for("history"))
    if request.method == "POST":
        if request.form.get("action") == "confirm":
            database.claim_assessments(claim_sid, current_user.id)
        session.pop("claim_sid", None)
        return redirect(url_for("history"))
    return render_template("claim.html", checks=checks)



@app.route("/", methods=["GET"])
def index():
    return render_template("home.html")


@app.route("/assessment", methods=["GET"])
def assessment():
    return render_template("assessment.html")


@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


@app.route("/report", methods=["GET"])
def report():
    """Serve standalone client-side report viewer shell without medical data."""
    return render_template("report_viewer.html")


@app.route("/health", methods=["GET"])
@limiter.exempt
def health():
    db_ok = True
    try:
        conn = database.get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Health check DB probe failed: {e}")
        db_ok = False

    models_loaded = list(MODELS.keys())
    healthy = db_ok and len(models_loaded) == len(CATEGORIES)
    status_code = 200 if healthy else 503
    return {
        "status": "healthy" if healthy else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "models_loaded": models_loaded,
        "models_expected": CATEGORIES,
        "rule_version": RULE_VERSION,
    }, status_code


def explain_patient_risk(patient: dict) -> dict:
    """
    Computes patient-specific clinical risk drivers for each complication domain,
    identifying the specific lifestyle, biometric, and clinical history factors
    that elevate this individual's risk score.
    """
    drivers = {
        "cardiovascular": [],
        "general_burden": [],
        "neuropathy_mobility": [],
        "retinopathy": [],
    }

    # Cardiovascular drivers (ACC/AHA)
    if patient.get("HeartDiseaseorAttack") == 1:
        drivers["cardiovascular"].append({
            "factor": "Prior Heart Attack / CAD",
            "impact": "High",
            "badge": "bg-red-100 text-red-700 border-red-200",
            "detail": "Secondary prevention risk multiplier (established coronary disease)."
        })
    if patient.get("Stroke") == 1:
        drivers["cardiovascular"].append({
            "factor": "Prior Stroke",
            "impact": "High",
            "badge": "bg-red-100 text-red-700 border-red-200",
            "detail": "Prior cerebrovascular event indicates advanced systemic arterial disease."
        })
    if patient.get("HighBP") == 1:
        drivers["cardiovascular"].append({
            "factor": "Hypertension (High BP)",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Increases systemic vascular afterload and arterial wall shear stress."
        })
    if patient.get("Smoker") == 1:
        drivers["cardiovascular"].append({
            "factor": "Active Smoking History",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Accelerates atherogenesis and endothelial dysfunction in diabetes."
        })
    if patient.get("HighChol") == 1:
        drivers["cardiovascular"].append({
            "factor": "High Cholesterol / Dyslipidemia",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Promotes atherogenic arterial lipid accumulation."
        })
    bmi = patient.get("BMI", 0)
    if bmi >= 30:
        drivers["cardiovascular"].append({
            "factor": f"Obesity (BMI {bmi})",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Elevates metabolic load, insulin resistance, and cardiac workload."
        })
    elif bmi >= 25:
        drivers["cardiovascular"].append({
            "factor": f"Overweight (BMI {bmi})",
            "impact": "Mild",
            "badge": "bg-slate-100 text-slate-700 border-slate-200",
            "detail": "Mild elevated metabolic and cardiovascular strain."
        })
    age_band = patient.get("Age", 0)
    if age_band >= 9:
        drivers["cardiovascular"].append({
            "factor": "Age ≥60 years",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Cumulative arterial stiffness and lifetime vascular exposure."
        })
    elif age_band >= 6:
        drivers["cardiovascular"].append({
            "factor": "Age 45–59 years",
            "impact": "Mild",
            "badge": "bg-slate-100 text-slate-700 border-slate-200",
            "detail": "Moderate cardiovascular age-related risk progression."
        })

    # Nephropathy / Chronic Kidney Disease drivers (KDIGO)
    if patient.get("HighBP") == 1:
        drivers["general_burden"].append({
            "factor": "Hypertension (High BP)",
            "impact": "High",
            "badge": "bg-red-100 text-red-700 border-red-200",
            "detail": "Primary hemodynamic risk driver for glomerular hyperfiltration and renal decline."
        })
    gen_hlth = patient.get("GenHlth", 1)
    if gen_hlth >= 4:
        drivers["general_burden"].append({
            "factor": "Fair / Poor General Health",
            "impact": "High",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Reflects multisystem burden and chronic vascular strain."
        })
    if bmi >= 30:
        drivers["general_burden"].append({
            "factor": f"Elevated BMI ({bmi})",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Associated with obesity-related glomerulopathy and hyperfiltration."
        })
    if patient.get("Smoker") == 1:
        drivers["general_burden"].append({
            "factor": "Active Smoking History",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Accelerates microvascular renal arteriosclerosis."
        })
    if patient.get("MentHlth", 0) >= 15:
        drivers["general_burden"].append({
            "factor": "Frequent Mental Distress",
            "impact": "Mild",
            "badge": "bg-slate-100 text-slate-700 border-slate-200",
            "detail": "Linked to increased systemic stress and lower treatment adherence."
        })
    if patient.get("NoDocbcCost") == 1:
        drivers["general_burden"].append({
            "factor": "Medical Care Cost Barrier",
            "impact": "Mild",
            "badge": "bg-slate-100 text-slate-700 border-slate-200",
            "detail": "Signals risk of delayed laboratory screening and surveillance."
        })

    # Neuropathy & Mobility drivers (MNSI)
    if patient.get("DiffWalk") == 1:
        drivers["neuropathy_mobility"].append({
            "factor": "Difficulty Walking / Climbing Stairs",
            "impact": "High",
            "badge": "bg-red-100 text-red-700 border-red-200",
            "detail": "Cardinal functional sign of lower-extremity peripheral diabetic neuropathy."
        })
    phys_hlth = patient.get("PhysHlth", 0)
    if phys_hlth >= 15:
        drivers["neuropathy_mobility"].append({
            "factor": f"Severe Physical Deficit ({phys_hlth} days/mo)",
            "impact": "High",
            "badge": "bg-red-100 text-red-700 border-red-200",
            "detail": "Persistent disability and reduced lower-extremity physical function."
        })
    elif phys_hlth >= 5:
        drivers["neuropathy_mobility"].append({
            "factor": f"Physical Health Deficit ({phys_hlth} days/mo)",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Early functional limitations impacting daily mobility."
        })
    if gen_hlth >= 4:
        drivers["neuropathy_mobility"].append({
            "factor": "Fair / Poor Health Rating",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Systemic frailty indicator associated with neuropathy severity."
        })
    if patient.get("Smoker") == 1:
        drivers["neuropathy_mobility"].append({
            "factor": "Active Smoking History",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Ischemia to vasa nervorum (microscopic peripheral nerve capillary supply)."
        })
    if age_band >= 9:
        drivers["neuropathy_mobility"].append({
            "factor": "Age ≥60 years",
            "impact": "Mild",
            "badge": "bg-slate-100 text-slate-700 border-slate-200",
            "detail": "Age-related peripheral nerve conduction reduction."
        })

    # Diabetic Retinopathy & Vision Loss drivers (ADA / UKPDS)
    dur = patient.get("DiabetesDuration", 0)
    if dur >= 3:
        drivers["retinopathy"].append({
            "factor": "Diabetes Duration ≥10 Years",
            "impact": "High",
            "badge": "bg-red-100 text-red-700 border-red-200",
            "detail": "Primary epidemiological risk factor for diabetic microvascular retinal capillary breakdown."
        })
    elif dur == 2:
        drivers["retinopathy"].append({
            "factor": "Diabetes Duration 5–9 Years",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Cumulative duration threshold where early microaneurysms and exudates become prevalent."
        })

    if patient.get("BlurryVision") == 1:
        drivers["retinopathy"].append({
            "factor": "Frequent Blurry Vision / Floaters",
            "impact": "High",
            "badge": "bg-red-100 text-red-700 border-red-200",
            "detail": "Cardinal subjective symptom associated with macular edema or vitreous microvascular changes."
        })
    if patient.get("HighBP") == 1:
        drivers["retinopathy"].append({
            "factor": "Hypertension (High BP)",
            "impact": "Moderate",
            "badge": "bg-amber-100 text-amber-800 border-amber-200",
            "detail": "Elevates hydrostatic shear stress on delicate retinal capillary walls."
        })
    if patient.get("HighChol") == 1:
        drivers["retinopathy"].append({
            "factor": "Dyslipidemia / High Cholesterol",
            "impact": "Mild",
            "badge": "bg-slate-100 text-slate-700 border-slate-200",
            "detail": "Associated with retinal hard exudate formation and capillary leakage."
        })
    if patient.get("Smoker") == 1:
        drivers["retinopathy"].append({
            "factor": "Active Smoking History",
            "impact": "Mild",
            "badge": "bg-slate-100 text-slate-700 border-slate-200",
            "detail": "Promotes microvascular vasoconstriction and relative retinal hypoxia."
        })

    for cat in drivers:
        if not drivers[cat]:
            drivers[cat].append({
                "factor": "No Elevated Risk Factors Identified",
                "impact": "Protective",
                "badge": "bg-emerald-100 text-emerald-800 border-emerald-200",
                "detail": "Reported indicators reflect baseline glycemic and preventative control."
            })

    return drivers


@app.route("/predict", methods=["POST"])
@limiter.limit("20 per minute")
def predict():
    patient, lab_values, errors = validate_patient_form(request.form)

    if errors:
        logger.warning("Form validation failed")
        return render_template(
            "assessment.html",
            errors=errors,
            form_data=request.form,
        ), 400

    rule_results = compute_all_risks(patient)
    logger.info("Rule matrix assessment completed")

    lab_assessment = compute_lab_assessment(
        hba1c=lab_values.get("LabHbA1c"),
        systolic_bp=lab_values.get("LabSystolicBP"),
        ldl=lab_values.get("LabLDL"),
    )

    model_results = {}
    model_confidences = {}
    model_metadata = {}
    if MODELS:
        X = pd.DataFrame([patient])[FEATURE_COLUMNS]
        for cat in CATEGORIES:
            if cat in MODELS:
                model = MODELS[cat]
                if hasattr(model, "predict_proba"):
                    if hasattr(model, "predict_with_probability"):
                        predictions, probabilities = model.predict_with_probability(X)
                        pred = predictions[0]
                        risk_pct = round(probabilities[0] * 100, 1)
                    else:
                        pred = model.predict(X)[0]
                        proba = model.predict_proba(X)[0]
                        risk_pct = round(proba[1] * 100, 1) if len(proba) == 2 else round(max(proba) * 100, 1)
                    model_results[cat] = pred
                    model_confidences[cat] = risk_pct
                else:
                    model_results[cat] = model.predict(X)[0]
                # Extract model quality metadata for UI display
                model_metadata[cat] = {
                    "model_status": getattr(model, "model_status", "validated"),
                    "calibration_quality": getattr(model, "calibration_quality", "fair"),
                    "uncertainty_level": getattr(model, "uncertainty_level", "moderate"),
                }

    save_history = request.form.get("save_history") == "1"
    assessment_id = None
    if save_history:
        assessment_id = database.save_assessment(
            session_id=session["session_id"],
            user_id=current_user.id if current_user.is_authenticated else None,
            patient=patient,
            rule_results=rule_results,
            model_results=model_results,
            lab_assessment=lab_assessment,
            model_confidences=model_confidences,
            model_names=MODEL_NAMES,
            rule_version=RULE_VERSION,
        )

    recommendations = build_recommendations(rule_results, lab_assessment)
    patient_drivers = explain_patient_risk(patient)

    report_payload = {
        "v": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rule_results": rule_results,
        "model_results": model_results,
        "model_confidences": model_confidences,
        "recommendations": recommendations,
        "patient_drivers": patient_drivers,
        "patient_summary": describe_patient(patient),
        "lab_assessment": lab_assessment,
    }
    report_payload_json = json.dumps(report_payload).replace("</", "<\\/")

    # Always generate a print token so the print button has a valid in-memory link,
    # regardless of whether the assessment was saved to the database.
    _prune_in_memory_assessments()
    print_id = str(uuid.uuid4())
    with _IN_MEMORY_LOCK:
        _IN_MEMORY_ASSESSMENTS[print_id] = {
            "is_print_token": True,
            "originating_session": session.get("session_id"),
            "patient": patient,
            "rule_results": rule_results,
            "model_results": model_results,
            "model_confidences": model_confidences,
            "model_names": MODEL_NAMES,
            "lab_assessment": lab_assessment,
            "created_at": report_payload["created_at"],
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }

    return render_template(
        "result.html",
        patient=patient,
        rule_results=rule_results,
        model_results=model_results,
        model_confidences=model_confidences,
        model_names=MODEL_NAMES,
        clinical_metrics=CLINICAL_METRICS,
        categories=CATEGORIES,
        lab_assessment=lab_assessment,
        recommendations=recommendations,
        patient_drivers=patient_drivers,
        assessment_id=assessment_id,
        print_id=print_id,
        model_metadata=model_metadata,
        report_payload_json=report_payload_json,
    )


@app.route("/print/<print_id>", methods=["GET"])
def print_current(print_id):
    _prune_in_memory_assessments()
    with _IN_MEMORY_LOCK:
        record = _IN_MEMORY_ASSESSMENTS.get(print_id)
    
    if not record:
        return redirect(url_for("assessment"))
        
    had_cookie = app.config.get("SESSION_COOKIE_NAME", "session") in request.cookies
    if had_cookie and session.get("session_id") != record.get("originating_session"):
        abort(403)
        
    # Don't pop the token here — let TTL-based expiration handle cleanup.
    # This allows the user to re-open the print page within the TTL window
    # (e.g. if the browser print dialog was dismissed accidentally).

    patient_drivers = explain_patient_risk(record["patient"])
    print_model_metadata = {}
    for pcat in CATEGORIES:
        if pcat in MODELS:
            pmodel = MODELS[pcat]
            print_model_metadata[pcat] = {
                "model_status": getattr(pmodel, "model_status", "validated"),
                "calibration_quality": getattr(pmodel, "calibration_quality", "fair"),
                "uncertainty_level": getattr(pmodel, "uncertainty_level", "moderate"),
            }
            
    return render_template(
        "print_result.html",
        assessment_id=None,
        created_at=record["created_at"],
        patient_display=describe_patient(record["patient"]),
        rule_results=record["rule_results"],
        model_results=record["model_results"],
        model_confidences=record.get("model_confidences", {}),
        model_names=record.get("model_names") or MODEL_NAMES,
        categories=CATEGORIES,
        lab_assessment=record.get("lab_assessment"),
        recommendations=build_recommendations(record["rule_results"], record.get("lab_assessment")),
        patient_drivers=patient_drivers,
        model_metadata=print_model_metadata,
    )


@app.route("/history", methods=["GET"])
def history():
    show_archived = request.args.get("view") == "archived"
    sort_order = request.args.get("sort", "desc").lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    # Always fetch in asc order first to establish baseline chronological numbering (1, 2, 3...)
    asc_records = database.get_all_assessments(
        session_id=session["session_id"],
        user_id=current_user.id if current_user.is_authenticated else None,
        archived=show_archived,
        sort_order="asc",
    )
    for idx, r in enumerate(asc_records, start=1):
        r["display_index"] = idx

    # If user selected desc (newest first), reverse the display list while keeping the chronological index intact
    records = asc_records if sort_order == "asc" else list(reversed(asc_records))

    return render_template(
        "history.html",
        records=records,
        categories=CATEGORIES,
        show_archived=show_archived,
        sort_order=sort_order,
    )


@app.route("/history/<int:assessment_id>/archive", methods=["POST"])
def archive_assessment(assessment_id):
    archived = request.form.get("archived") == "1"
    came_from_archived = request.form.get("from") == "archived"
    updated = database.set_archived(
        assessment_id,
        session_id=session["session_id"],
        user_id=current_user.id if current_user.is_authenticated else None,
        archived=archived,
    )
    if not updated:
        abort(404)
    return redirect(url_for("history", view="archived" if came_from_archived else None))


@app.route("/history/<int:assessment_id>/delete", methods=["POST"])
def delete_assessment(assessment_id):
    came_from_archived = request.form.get("from") == "archived"
    if current_user.is_authenticated:
        deleted = database.delete_owned_assessment(assessment_id, current_user.id)
    else:
        deleted = database.delete_assessment(assessment_id, session_id=session["session_id"])
    if not deleted:
        abort(404)
    return redirect(url_for("history", view="archived" if came_from_archived else None))


@app.route("/history/<int:assessment_id>", methods=["GET"])
def history_detail(assessment_id):
    record = database.get_assessment(
        assessment_id,
        session_id=session["session_id"],
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    if not record:
        abort(404)
    patient_drivers = explain_patient_risk(record["patient"])
    # Build model metadata from currently loaded models
    hist_model_metadata = {}
    for hcat in CATEGORIES:
        if hcat in MODELS:
            hmodel = MODELS[hcat]
            hist_model_metadata[hcat] = {
                "model_status": getattr(hmodel, "model_status", "validated"),
                "calibration_quality": getattr(hmodel, "calibration_quality", "fair"),
                "uncertainty_level": getattr(hmodel, "uncertainty_level", "moderate"),
            }
    recommendations = build_recommendations(record["rule_results"], record.get("lab_assessment"))
    report_payload = {
        "v": 1,
        "created_at": record["created_at"],
        "rule_results": record["rule_results"],
        "model_results": record["model_results"],
        "model_confidences": record.get("model_confidences", {}),
        "recommendations": recommendations,
        "patient_drivers": patient_drivers,
        "patient_summary": describe_patient(record["patient"]),
        "lab_assessment": record.get("lab_assessment"),
    }
    report_payload_json = json.dumps(report_payload).replace("</", "<\\/")

    return render_template(
        "result.html",
        patient=record["patient"],
        rule_results=record["rule_results"],
        model_results=record["model_results"],
        model_confidences=record.get("model_confidences", {}),
        model_names=record.get("model_names") or MODEL_NAMES,
        clinical_metrics=CLINICAL_METRICS,
        categories=CATEGORIES,
        lab_assessment=record.get("lab_assessment"),
        recommendations=recommendations,
        patient_drivers=patient_drivers,
        viewing_past=True,
        created_at=record["created_at"],
        assessment_id=assessment_id,
        model_metadata=hist_model_metadata,
        report_payload_json=report_payload_json,
    )



@app.route("/history/<int:assessment_id>/print", methods=["GET"])
def print_result(assessment_id):
    record = database.get_assessment(
        assessment_id,
        session_id=session["session_id"],
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    if not record:
        abort(404)
    patient_drivers = explain_patient_risk(record["patient"])
    # Build model metadata from currently loaded models
    print_model_metadata = {}
    for pcat in CATEGORIES:
        if pcat in MODELS:
            pmodel = MODELS[pcat]
            print_model_metadata[pcat] = {
                "model_status": getattr(pmodel, "model_status", "validated"),
                "calibration_quality": getattr(pmodel, "calibration_quality", "fair"),
                "uncertainty_level": getattr(pmodel, "uncertainty_level", "moderate"),
            }
    return render_template(
        "print_result.html",
        assessment_id=assessment_id,
        created_at=record["created_at"],
        patient_display=describe_patient(record["patient"]),
        rule_results=record["rule_results"],
        model_results=record["model_results"],
        model_confidences=record.get("model_confidences", {}),
        model_names=record.get("model_names") or MODEL_NAMES,
        categories=CATEGORIES,
        lab_assessment=record.get("lab_assessment"),
        recommendations=build_recommendations(record["rule_results"], record.get("lab_assessment")),
        patient_drivers=patient_drivers,
        model_metadata=print_model_metadata,
    )


@app.post("/feedback/<int:assessment_id>")
def feedback(assessment_id):
    record = database.get_assessment(
        assessment_id,
        session_id=session["session_id"],
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    if not record:
        abort(404)
    helpful = request.form.get("helpful") == "1"
    database.save_feedback(assessment_id, helpful, request.form.get("comment"))
    return redirect(url_for("history_detail", assessment_id=assessment_id))


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f"CSRF validation failed: {e.description}")
    return render_template(
        "assessment.html",
        errors=["Security validation failed (CSRF token missing or expired). Please resubmit."],
        form_data={},
    ), 400


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    logger.exception("Unexpected server error")
    return render_template(
        "assessment.html",
        errors=["An error occurred while processing your assessment. Please check your inputs and try again."],
        form_data={},
    ), 500


@app.cli.command("create-admin")
def create_admin_command():
    """Create an administrator account from the command line."""
    email = click.prompt("Email").strip().lower()
    display_name = click.prompt("Nickname").strip()
    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    if database.get_user_by_email(email):
        raise click.ClickException("An account with that email already exists.")
    if not display_name or len(display_name) > 40 or _password_error(password, email):
        raise click.ClickException("Enter a valid nickname and password.")
    user_id = database.create_user(
        email,
        password,
        display_name,
        consent_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        role="admin",
    )
    click.echo(f"Created admin account {user_id}.")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=DEBUG)
