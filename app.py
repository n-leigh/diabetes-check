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
from flask import Flask, current_app, render_template, request, redirect, url_for, session, abort, jsonify
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
from progress_tracker import build_progress_view
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_STARTED_AT = datetime.now(timezone.utc)
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
        self._password_fingerprint = hashlib.sha256(
            row["password_hash"].encode("utf-8")
        ).hexdigest()

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = bool(value)

    def get_id(self):
        return f"{self.id}:{self._password_fingerprint}"


@login_manager.user_loader
def load_user(user_id):
    try:
        raw_id, fingerprint = str(user_id).split(":", 1)
        row = database.get_user_by_id(int(raw_id))
    except (TypeError, ValueError):
        return None
    if not row:
        return None
    expected = hashlib.sha256(row["password_hash"].encode("utf-8")).hexdigest()
    return AuthUser(row) if secrets.compare_digest(expected, fingerprint) else None


_DUMMY_PASSWORD_HASH = generate_password_hash("dummy-password-for-timing", method="scrypt")
_verification_resend_lock = threading.Lock()
_verification_resend_times = {}
_verification_resend_history = {}
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


def _admin_count(value):
    return str(value) if value >= 5 else "<5"


def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable units (KB/MB)."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} bytes"


def _format_uptime(started_at) -> str:
    """Format process uptime into plain-language days and hours."""
    delta = datetime.now(timezone.utc) - started_at
    days = delta.days
    hours = delta.seconds // 3600
    return f"Running for {days} days {hours} hours"


def _admin_feedback_tally():
    """Compute aggregate helpful vs unhelpful feedback with small-cell suppression."""
    conn = database.get_connection()
    try:
        feedback_total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        helpful_total = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE helpful = ?", (True,)
        ).fetchone()[0]
        unhelpful_total = feedback_total - helpful_total
        # Statistical disclosure control: if either helpful or unhelpful count is < 5,
        # suppress both counts so the small count cannot be calculated from the total.
        if helpful_total < 5 or unhelpful_total < 5:
            yes_display = "<5"
            no_display = "<5"
        else:
            yes_display = str(helpful_total)
            no_display = str(unhelpful_total)
        return {
            "yes": yes_display,
            "no": no_display,
            "text": f"Helpful: {yes_display} yes / {no_display} no",
        }
    finally:
        conn.close()


def _sanitize_csv_cell(value):
    """Neutralize potential CSV formula injection (=, +, -, @)."""
    s = str(value) if value is not None else ""
    if s and s[0] in ("=", "+", "-", "@"):
        return f"'{s}"
    return s


ADMIN_DOMAIN_TITLES = (
    ("cardiovascular", "Heart"),
    ("general_burden", "Kidneys"),
    ("neuropathy_mobility", "Nerves and feet"),
    ("retinopathy", "Eyes"),
)


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
        helpful_total = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE helpful = ?", (True,)
        ).fetchone()[0]
        unhelpful_total = feedback_total - helpful_total
        if helpful_total < 5 or unhelpful_total < 5:
            feedback_helpful_rate = "<5 responses"
        else:
            feedback_helpful_rate = f"{helpful_total / feedback_total:.0%}"
        status_counts = {}
        for category, title in ADMIN_DOMAIN_TITLES:
            rows = conn.execute(
                """SELECT rule_label, COUNT(*) AS total FROM risk_results
                   WHERE category = ? GROUP BY rule_label""",
                (category,),
            ).fetchall()
            raw_counts = {
                "Good": 0,
                "Check": 0,
                "See a doctor": 0,
            }
            for row in rows:
                label = get_status_presentation(row["rule_label"])["label"]
                raw_counts[label] = row["total"]

            # Statistical disclosure control / Tightened secondary suppression rule (Requirement 3.1f / Item 4):
            # If ANY status cell in a domain is below 5, display all three cells for that domain as "<5".
            # This completely prevents deriving any hidden small count from domain or platform totals.
            if any(count < 5 for count in raw_counts.values()):
                status_counts[title] = {
                    "Good": "<5",
                    "Check": "<5",
                    "See a doctor": "<5",
                }
            else:
                status_counts[title] = {
                    label: str(count)
                    for label, count in raw_counts.items()
                }
        days = []
        for offset in range(29, -1, -1):
            day = (now - timedelta(days=offset)).date()
            count = conn.execute(
                "SELECT COUNT(*) FROM assessments WHERE date(created_at) = ?",
                (day.isoformat(),),
            ).fetchone()[0]
            days.append({
                "date": day.isoformat(),
                "display_count": _admin_count(count),
                "bar_width": min(count * 12, 100) if count >= 5 else 0,
            })
        return {
            "users_total": _admin_count(users_total),
            "new_users": _admin_count(new_users),
            "assessments_total": _admin_count(assessments_total),
            "feedback_helpful_rate": feedback_helpful_rate,
            "status_counts": status_counts,
            "days": days,
        }
    finally:
        conn.close()


def _safe_next_url(value, fallback=None):
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return fallback or url_for("history")


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

    # Enforce strict Cache-Control for sensitive clinical and admin routes
    if (
        request.path == "/predict"
        or request.path.startswith("/print")
        or request.path.startswith("/history")
        or request.path.startswith("/result")
        or request.path == "/admin"
        or request.path.startswith("/admin/")
    ):
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
LIVE_DB_CHECKS = (
    os.getenv("ALLOW_LIVE_DB_CHECKS") == "1"
    and os.getenv("LIVE_DB_BACKUP_CONFIRMED") == "1"
)
try:
    RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))
except ValueError:
    logger.warning("Invalid RETENTION_DAYS; falling back to 90.")
    RETENTION_DAYS = 90

if RETENTION_DAYS < 1:
    logger.warning("RETENTION_DAYS must be >= 1; falling back to 90.")
    RETENTION_DAYS = 90

LAST_PRUNED_COUNT = 0
if not LIVE_DB_CHECKS:
    try:
        pruned_count = database.prune_expired_assessments(days=RETENTION_DAYS)
    except Exception:
        logger.exception("Failed to prune expired assessments")
        pruned_count = 0
    LAST_PRUNED_COUNT = pruned_count
    if pruned_count:
        logger.info("Expired assessments pruned: %d", pruned_count)
    try:
        pruned_unverified = database.prune_unverified_accounts(days=7)
    except Exception:
        logger.exception("Failed to prune stale unverified accounts")
        pruned_unverified = 0
    if pruned_unverified:
        logger.info("Stale unverified accounts pruned: %d", pruned_unverified)

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


def _send_reset_email(email, reset_link, display_name=""):
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
    message["Subject"] = "Reset your DiaBeates password"
    message["From"] = smtp_from
    message["To"] = email
    message.set_content(render_template("emails/password_reset.txt", display_name=display_name, reset_link=reset_link, minutes=30))
    message.add_alternative(render_template("emails/password_reset.html", display_name=display_name, reset_link=reset_link, minutes=30), subtype="html")
    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        server.starttls()
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.send_message(message)
    return True


def _send_email_template(email, subject, html_template, text_template, **context):
    if not _smtp_configured():
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.getenv("SMTP_FROM", "").strip()
    message["To"] = email
    message.set_content(render_template(text_template, **context))
    message.add_alternative(render_template(html_template, **context), subtype="html")
    with smtplib.SMTP(os.getenv("SMTP_HOST", "").strip(), int(os.getenv("SMTP_PORT", "587")), timeout=10) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USER", "").strip(), os.getenv("SMTP_PASSWORD", ""))
        server.send_message(message)
    return True


def _send_email_async(email, subject, html_template, text_template, **context):
    application = current_app._get_current_object()

    def deliver():
        try:
            with application.app_context():
                _send_email_template(email, subject, html_template, text_template, **context)
        except (OSError, smtplib.SMTPException, ValueError):
            logger.warning("Non-critical email delivery failed for configured account notification.")
    threading.Thread(
        target=deliver,
        daemon=True,
    ).start()


def _datetime_pht():
    return datetime.now(timezone.utc).astimezone(DISPLAY_ZONE).strftime("%Y-%m-%d %H:%M PHT")


def _smtp_configured():
    return all(os.getenv(name, "").strip() for name in (
        "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"
    ))


def _email_verification_required():
    value = os.getenv("REQUIRE_EMAIL_VERIFICATION")
    if value is None or not value.strip():
        return True
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _verification_link(token):
    base_url = os.getenv("BASE_URL", "").strip().rstrip("/")
    path = url_for("verify_email", token=token)
    return f"{base_url}{path}" if base_url else url_for("verify_email", token=token, _external=True)


def _site_link(path):
    base_url = os.getenv("BASE_URL", "").strip().rstrip("/")
    return f"{base_url}{path}" if base_url else path


def _send_verification_email(email, display_name, verification_link):
    if not _smtp_configured():
        return False
    message = EmailMessage()
    message["Subject"] = "Confirm your DiaBeates email"
    message["From"] = os.getenv("SMTP_FROM", "").strip()
    message["To"] = email
    message.set_content(render_template("emails/verification.txt", display_name=display_name, verification_link=verification_link))
    message.add_alternative(render_template("emails/verification.html", display_name=display_name, verification_link=verification_link), subtype="html")
    with smtplib.SMTP(os.getenv("SMTP_HOST", "").strip(), int(os.getenv("SMTP_PORT", "587")), timeout=10) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USER", "").strip(), os.getenv("SMTP_PASSWORD", ""))
        server.send_message(message)
    return True


def _send_welcome_email(email, display_name):
    return _send_email_template(
        email, "Welcome to DiaBeates", "emails/welcome.html", "emails/welcome.txt",
        display_name=display_name,
    )


def _create_verification_message(user_id, email, display_name):
    raw_token = secrets.token_urlsafe(32)
    database.create_email_verification_token(
        user_id,
        hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(timespec="seconds"),
    )
    return _send_verification_email(email, display_name, _verification_link(raw_token))


def _resend_allowed(email):
    now = datetime.now(timezone.utc).timestamp()
    with _verification_resend_lock:
        last_sent = _verification_resend_times.get(email)
        history = [timestamp for timestamp in _verification_resend_history.get(email, []) if now - timestamp < 3600]
        if (last_sent and now - last_sent < 60) or len(history) >= 5:
            return False
        _verification_resend_times[email] = now
        history.append(now)
        _verification_resend_history[email] = history
        return True


if not _smtp_configured() and not _email_verification_required():
    logger.warning("SMTP is not fully configured; new accounts will be auto-verified.")
elif not _smtp_configured() and _email_verification_required():
    logger.warning("Email verification is required but SMTP is not fully configured; registration is disabled.")


def _reset_link(token):
    base_url = os.getenv("BASE_URL", "").strip().rstrip("/")
    if base_url:
        return f"{base_url}{url_for('reset_password', token=token)}"
    return url_for("reset_password", token=token, _external=True)


def _post_auth_redirect(next_url=None):
        is_admin = current_user.is_authenticated and current_user.role == "admin"
        fallback_url = url_for("admin_dashboard") if is_admin else url_for("history")
        destination = _safe_next_url(next_url, fallback_url)
        if is_admin:
            destination_path = destination.split("?", 1)[0].split("#", 1)[0]
            admin_url = url_for("admin_dashboard")
            account_url = url_for("account")
            if not (
                destination_path == admin_url
                or destination_path.startswith(f"{admin_url}/")
                or destination_path == account_url
                or destination_path.startswith(f"{account_url}/")
            ):
                destination = fallback_url
            return redirect(destination)
        claim_sid = session.get("claim_sid")
        if claim_sid and database.get_unclaimed_assessments(claim_sid):
            return redirect(url_for("claim"))
        return redirect(destination)


@app.before_request
def ensure_session_id():
    if current_user.is_authenticated and current_user.role == "admin":
        last_seen = session.get("admin_last_seen")
        now = datetime.now(timezone.utc).timestamp()
        if last_seen and now - last_seen > 1800:
            logout_user()
            session.pop("admin_last_seen", None)
            return redirect(url_for("login", next=url_for("admin_dashboard")))
        session["admin_last_seen"] = now
        allowed_admin_path = (
            request.path == url_for("admin_dashboard")
            or request.path.startswith(f"{url_for('admin_dashboard')}/")
            or request.path == url_for("account")
            or request.path.startswith(f"{url_for('account')}/")
            or request.path == url_for("logout")
            or request.path == url_for("health")
            or request.endpoint == "static"
        )
        if not allowed_admin_path:
            return redirect(url_for("admin_dashboard"))
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session.permanent = True


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return _post_auth_redirect(request.args.get("next"))
    errors = []
    if request.method == "POST":
        display_name = re.sub(r"[\r\n]+", " ", request.form.get("nickname", "").strip())
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
        if _email_verification_required() and not _smtp_configured():
            errors.append("Email sign-up is temporarily unavailable. Please try again later.")
        if not errors:
            existing = database.get_user_by_email(email)
            if existing and existing["email_verified_at"]:
                errors.append("That email is already registered.")
            else:
                try:
                    if existing:
                        user_id = existing["id"]
                        conn = database.get_connection()
                        try:
                            conn.execute(
                                "UPDATE users SET display_name = ?, password_hash = ?, email_verified_at = NULL, "
                                "consent_at = ?, consent_version = ?, created_at = ? WHERE id = ?",
                                (display_name, generate_password_hash(password, method="scrypt"),
                                 datetime.now(timezone.utc).isoformat(timespec="seconds"), "1.0",
                                 datetime.now(timezone.utc).isoformat(timespec="seconds"), user_id),
                            )
                            conn.commit()
                        finally:
                            conn.close()
                        raw_token = secrets.token_urlsafe(32)
                        database.create_email_verification_token(
                            user_id,
                            hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                            (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(timespec="seconds"),
                        )
                        sent = _send_verification_email(email, display_name, _verification_link(raw_token))
                    else:
                        verified_at = None if _email_verification_required() else datetime.now(timezone.utc).isoformat(timespec="seconds")
                        user_id = database.create_user(email, password, display_name, email_verified_at=verified_at)
                        sent = True if verified_at else _create_verification_message(user_id, email, display_name)
                except (OSError, smtplib.SMTPException, ValueError):
                    logger.warning("Verification email delivery failed for a pending account.")
                    sent = False
                except sqlite3.IntegrityError:
                    errors.append("That email is already registered.")
                else:
                    if not sent and _email_verification_required():
                        errors.append("We could not send the confirmation email. Please try again.")
                    elif _email_verification_required():
                        database.log_audit("verification_sent", str(user_id), None, get_remote_address())
                        session["pending_verification_email"] = email
                        return redirect(url_for("check_email"))
                    else:
                        return redirect(url_for("login"))
    return render_template("register.html", errors=errors, form_data=request.form)


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return _post_auth_redirect(request.args.get("next"))
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
        elif not row["email_verified_at"]:
            errors.append("Please confirm your email first.")
            session["pending_verification_email"] = email
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
    return render_template(
        "login.html",
        errors=errors,
        form_data=request.form,
        unverified_email=session.get("pending_verification_email") if any(
            "confirm your email" in error.lower() for error in errors
        ) else None,
    )


@app.get("/check-email")
def check_email():
    email = session.get("pending_verification_email")
    if not email:
        return redirect(url_for("register"))
    return render_template("check_email.html", email=email)


@app.post("/resend-verification")
@limiter.limit("5 per hour")
def resend_verification():
    email = request.form.get("email", "").strip().lower()
    row = database.get_user_by_email(email)
    if row and not row["email_verified_at"] and _resend_allowed(email):
        try:
            if _create_verification_message(row["id"], row["email"], row["display_name"]):
                database.log_audit("verification_sent", str(row["id"]), None, get_remote_address())
                database.log_audit("resend_requested", str(row["id"]), None, get_remote_address())
        except (OSError, smtplib.SMTPException, ValueError):
            logger.warning("Verification resend failed for a pending account.")
    session["pending_verification_email"] = email
    return render_template("check_email.html", email=email, resend_submitted=True)


@app.route("/verify-email/<token>", methods=["GET", "POST"])
def verify_email(token):
    token_row = database.get_email_verification_token(
        hashlib.sha256(token.encode("utf-8")).hexdigest()
    )
    if request.method == "GET":
        if not token_row:
            return render_template("verify_email.html", state="invalid")
        user = database.get_user_by_id(token_row["user_id"])
        if user and user["email_verified_at"]:
            return render_template("verify_email.html", state="already_verified")
        return render_template("verify_email.html", state="confirm", token=token)
    if not token_row:
        return render_template("verify_email.html", state="invalid")
    verified_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not database.consume_email_verification_token(token_row["id"], token_row["user_id"], verified_at):
        return render_template("verify_email.html", state="invalid")
    user = database.get_user_by_id(token_row["user_id"])
    database.log_audit("verified", str(token_row["user_id"]), None, get_remote_address())
    try:
        _send_welcome_email(user["email"], user["display_name"])
    except (OSError, smtplib.SMTPException, ValueError):
        logger.warning("Welcome email delivery failed after verification.")
    return render_template("verify_email.html", state="verified")


@app.post("/logout")
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    remember_action = session.pop("_remember", None)
    session.clear()
    if remember_action:
        session["_remember"] = remember_action
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
    display_name = re.sub(r"[\r\n]+", " ", request.form.get("nickname", "").strip())
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
        _send_email_async(
            row["email"], "Your DiaBeates password was changed",
            "emails/password_changed.html", "emails/password_changed.txt",
            display_name=row["display_name"], datetime_pht=_datetime_pht(),
            reset_link=_site_link("/forgot-password"),
        )
        message = "Your password was changed."
    return redirect(url_for("account", message=message))


@app.post("/account/delete")
@login_required
def account_delete():
    row = database.get_user_by_id(current_user.id)
    if not check_password_hash(row["password_hash"], request.form.get("current_password", "")):
        return redirect(url_for("account", message="Your current password is incorrect."))
    user_id = current_user.id
    deleted_email = row["email"]
    deleted_name = row["display_name"]
    database.log_audit("account_deleted", str(user_id), user_id, get_remote_address())
    database.delete_user_account(user_id)
    _send_email_async(
        deleted_email, "Your DiaBeates account was deleted",
        "emails/account_deleted.html", "emails/account_deleted.txt",
        display_name=deleted_name, datetime_pht=_datetime_pht(),
        assessment_link=_site_link("/assessment"),
    )
    logout_user()
    session.clear()
    return redirect(url_for("index", deleted="1"))


@app.get("/account/export")
@login_required
def account_export():
    user_row = database.get_user_by_id(current_user.id)
    records = database.get_all_assessments(
        session_id=session["session_id"], user_id=current_user.id, limit=10000, sort_order="asc"
    )
    payload = {
        "nickname": current_user.display_name,
        "email": current_user.email,
        "email_verified_at": user_row["email_verified_at"],
        "email_notifications": bool(user_row["email_notifications"]),
        "assessments": records,
    }
    response = app.response_class(
        json.dumps(payload, default=str, ensure_ascii=False),
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = "attachment; filename=diabeates-data.json"
    return response


@app.post("/account/email-notifications")
@login_required
def account_email_notifications():
    database.set_email_notifications(current_user.id, request.form.get("email_notifications") == "1")
    return redirect(url_for("account", message="Email preferences were saved."))


@app.get("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", dashboard=_admin_dashboard_data())


KNOWN_AUDIT_ACTIONS = [
    "login_success",
    "login_failed",
    "lockout",
    "logout",
    "password_changed",
    "password_reset_requested",
    "password_reset_completed",
    "account_deleted",
    "admin_user_deactivated",
    "admin_user_reactivated",
    "admin_user_deleted",
    "admin_reset_link_created",
    "admin_backup_created",
]


@app.get("/admin/users")
@admin_required
def admin_users():
    conn = database.get_connection()
    try:
        users = [dict(row) for row in conn.execute(
            """SELECT id, display_name, email, role, is_active, email_verified_at, created_at, last_login_at
               FROM users ORDER BY id DESC"""
        ).fetchall()]
    finally:
        conn.close()
    reset_link = session.pop("admin_reset_link", None)
    return render_template(
        "admin_users.html",
        users=users,
        reset_link=reset_link,
        active_admin_count=_active_admin_count(),
    )


def _active_admin_count():
    conn = database.get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = ?",
            (True,),
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
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (False, user_id))
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
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (True, user_id))
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
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50
    offset = (page - 1) * per_page
    conn = database.get_connection()
    try:
        max_allowed = max(0, 200 - offset)
        fetch_limit = min(per_page + 1, max_allowed)
        if fetch_limit > 0:
            raw_feedback = [dict(row) for row in conn.execute(
                """SELECT helpful, comment, created_at, NULL AS name FROM feedback
                   UNION ALL
                   SELECT NULL AS helpful, message AS comment, created_at, name
                   FROM feedback_submissions
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (fetch_limit, offset),
            ).fetchall()]
        else:
            raw_feedback = []
    finally:
        conn.close()

    has_next = len(raw_feedback) > per_page and (offset + per_page < 200)
    feedback = raw_feedback[:per_page]
    return render_template(
        "admin_feedback.html",
        feedback=feedback,
        tally=_admin_feedback_tally(),
        page=page,
        has_next=has_next,
        has_prev=(page > 1),
    )


@app.get("/admin/audit")
@admin_required
def admin_audit():
    page = max(1, request.args.get("page", 1, type=int))
    action = request.args.get("action", "").strip()
    per_page = 50
    offset = (page - 1) * per_page
    conn = database.get_connection()
    try:
        where = "WHERE action = ?" if action else ""
        params = (action, per_page + 1, offset) if action else (per_page + 1, offset)
        raw_audit = [dict(row) for row in conn.execute(
            f"""SELECT id, actor_user_id, action, target, created_at
                FROM audit_log {where} ORDER BY id DESC LIMIT ? OFFSET ?""",
            params,
        ).fetchall()]
    finally:
        conn.close()
    has_next = len(raw_audit) > per_page
    audit = raw_audit[:per_page]
    return render_template(
        "admin_audit.html",
        audit=audit,
        action=action,
        page=page,
        has_next=has_next,
        has_prev=(page > 1),
        known_actions=KNOWN_AUDIT_ACTIONS,
    )


@app.get("/admin/system")
@admin_required
def admin_system():
    if database.DB_BACKEND == "postgres":
        return render_template(
            "admin_system.html",
            backups=[],
            database_size=None,
            database_backend="postgres",
            model_names=MODEL_NAMES,
            retention_days=RETENTION_DAYS,
            backup_message=session.pop("backup_message", None),
        )
    backups_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    backups = []
    for name in sorted(os.listdir(backups_dir), reverse=True):
        if name.endswith(".zip"):
            bpath = os.path.join(backups_dir, name)
            try:
                bsize = format_file_size(os.path.getsize(bpath))
            except OSError:
                bsize = "Unknown size"
            backups.append({"name": name, "size": bsize})

    try:
        database_size = format_file_size(os.path.getsize(database.DB_PATH))
    except OSError:
        database_size = "0 bytes"

    health_info = _system_health_status()
    uptime = _format_uptime(APP_STARTED_AT)

    model_details = []
    for cat, title in ADMIN_DOMAIN_TITLES:
        model_details.append({
            "category": cat,
            "title": title,
            "name": MODEL_NAMES.get(cat, "Unknown model"),
            "status": CLINICAL_METRICS.get(cat, {}).get("model_status", "validated"),
            "is_loaded": cat in MODELS,
        })

    return render_template(
        "admin_system.html",
        backups=backups,
        database_size=database_size,
        health_info=health_info,
        uptime=uptime,
        model_details=model_details,
        database_backend=database.DB_BACKEND,
        model_names=MODEL_NAMES,
        retention_days=RETENTION_DAYS,
        last_pruned=LAST_PRUNED_COUNT,
        backup_message=session.pop("backup_message", None),
    )


@app.post("/admin/system/backup")
@admin_required
def admin_backup():
    if database.DB_BACKEND == "postgres":
        session["backup_message"] = "Backups are managed in Supabase or with pg_dump."
        return redirect(url_for("admin_system"))
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
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([_sanitize_csv_cell("metric"), _sanitize_csv_cell("value")])
    writer.writerow([_sanitize_csv_cell("generated_at"), _sanitize_csv_cell(now_iso)])
    writer.writerow([_sanitize_csv_cell("suppression_note"), _sanitize_csv_cell("Counts below 5 are shown as <5")])
    writer.writerow([_sanitize_csv_cell("total_users"), _sanitize_csv_cell(dashboard["users_total"])])
    writer.writerow([_sanitize_csv_cell("new_users_last_7_days"), _sanitize_csv_cell(dashboard["new_users"])])
    writer.writerow([_sanitize_csv_cell("total_assessments"), _sanitize_csv_cell(dashboard["assessments_total"])])
    writer.writerow([_sanitize_csv_cell("helpful_feedback_rate"), _sanitize_csv_cell(dashboard["feedback_helpful_rate"])])
    for title, counts in dashboard["status_counts"].items():
        for status, value in counts.items():
            key = f"{title.lower()}_{status.lower().replace(' ', '_')}"
            writer.writerow([_sanitize_csv_cell(key), _sanitize_csv_cell(value)])
    response = app.response_class(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=diabeates-admin-summary.csv"
    return response


@app.get("/history/progress")
def history_progress():
    include_archived = request.args.get("include_archived") == "1"
    ownership = {
        "session_id": session["session_id"],
        "user_id": current_user.id if current_user.is_authenticated else None,
        "limit": 200,
        "sort_order": "asc",
    }
    records = database.get_all_assessments(archived=False, **ownership)
    if include_archived:
        records.extend(database.get_all_assessments(archived=True, **ownership))
    for record in records:
        record["risk_drivers"] = [
            driver["factor"]
            for drivers in explain_patient_risk(record["patient"]).values()
            for driver in drivers
        ]
    compare_ids = [value for value in (
        request.args.get("before"),
        request.args.get("after"),
    ) if value]
    progress = build_progress_view(
        records,
        include_archived=include_archived,
        compare_ids=compare_ids or None,
    )
    progress["is_guest"] = not current_user.is_authenticated
    progress["print_url"] = url_for(
        "print_progress",
        include_archived="1" if include_archived else None,
        before=progress["comparison"]["before"]["id"] if progress["comparison"] else None,
        after=progress["comparison"]["after"]["id"] if progress["comparison"] else None,
    )
    return render_template("progress.html", **progress)


@app.get("/history/progress/print")
def print_progress():
    include_archived = request.args.get("include_archived") == "1"
    ownership = {
        "session_id": session["session_id"],
        "user_id": current_user.id if current_user.is_authenticated else None,
        "limit": 200,
        "sort_order": "asc",
    }
    records = database.get_all_assessments(archived=False, **ownership)
    if include_archived:
        records.extend(database.get_all_assessments(archived=True, **ownership))
    for record in records:
        record["risk_drivers"] = [
            driver["factor"]
            for drivers in explain_patient_risk(record["patient"]).values()
            for driver in drivers
        ]
    compare_ids = [value for value in (
        request.args.get("before"),
        request.args.get("after"),
    ) if value]
    progress = build_progress_view(
        records,
        include_archived=include_archived,
        compare_ids=compare_ids or None,
    )
    return render_template(
        "progress_print.html",
        **progress,
        generated_at=datetime.now(timezone.utc),
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
                (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds"),
            )
            link = _reset_link(raw_token)
            try:
                sent = _send_reset_email(row["email"], link, row["display_name"])
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
            if not database.complete_password_reset(token_row["id"], token_row["user_id"], password):
                errors.append("This reset link is invalid or expired.")
            else:
                database.mark_email_verified(token_row["user_id"])
                database.log_audit("password_reset_completed", str(token_row["user_id"]), token_row["user_id"], get_remote_address())
                user = database.get_user_by_id(token_row["user_id"])
                _send_email_async(
                    user["email"], "Your DiaBeates password was changed",
                    "emails/password_changed.html", "emails/password_changed.txt",
                    display_name=user["display_name"], datetime_pht=_datetime_pht(),
                    reset_link=_site_link("/forgot-password"),
                )
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


def _system_health_status():
    db_ok = True
    migration_pending = False
    try:
        conn = database.get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        migration_pending = not database.check_email_verification_schema()
    except Exception as e:
        logger.error(f"Health check DB probe failed: {e}")
        db_ok = False

    models_loaded = list(MODELS.keys())
    healthy = db_ok and not migration_pending and len(models_loaded) == len(CATEGORIES)
    status_code = 200 if healthy else 503
    return {
        "status": "healthy" if healthy else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "reason": "database migration pending" if migration_pending else None,
        "models_loaded": models_loaded,
        "models_loaded_count": len(models_loaded),
        "models_expected_count": len(CATEGORIES),
        "models_expected": CATEGORIES,
        "rule_version": RULE_VERSION,
    }


@app.route("/health", methods=["GET"])
@limiter.exempt
def health():
    info = _system_health_status()
    status_code = 200 if info["status"] == "healthy" else 503
    return {
        "status": info["status"],
        "database": info["database"],
        "models_loaded": info["models_loaded"],
        "models_expected": info["models_expected"],
        "rule_version": info["rule_version"],
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
    bmi = patient.get("BMI") or 0
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
    age_band = patient.get("Age") or 0
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
    gen_hlth = patient.get("GenHlth") or 1
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
    if (patient.get("MentHlth") or 0) >= 15:
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
    phys_hlth = patient.get("PhysHlth") or 0
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
    dur = patient.get("DiabetesDuration") or 0
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
        if current_user.is_authenticated:
            saved_user = database.get_user_by_id(current_user.id)
            if saved_user["email_notifications"]:
                _send_email_async(
                    saved_user["email"], "Your check was saved",
                    "emails/check_saved.html", "emails/check_saved.txt",
                    display_name=saved_user["display_name"],
                    datetime_pht=_datetime_pht(),
                    history_link=_site_link("/history"),
                )

    recommendations = build_recommendations(rule_results, lab_assessment, patient)
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
        recommendations=build_recommendations(
            record["rule_results"], record.get("lab_assessment"), record["patient"]
        ),
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


@app.get("/history/signature")
def history_signature():
    show_archived = request.args.get("view") == "archived"
    signature = database.get_assessment_history_signature(
        session_id=session["session_id"],
        user_id=current_user.id if current_user.is_authenticated else None,
        archived=show_archived,
    )
    return jsonify(signature)


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
    recommendations = build_recommendations(
        record["rule_results"], record.get("lab_assessment"), record["patient"]
    )
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
        recommendations=build_recommendations(
            record["rule_results"], record.get("lab_assessment"), record["patient"]
        ),
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


@app.post("/api/feedback")
def feedback_submission():
    name = request.form.get("name", "").strip()
    message = request.form.get("message", "").strip()
    errors = []
    if len(name) > 100:
        errors.append("Your name must be 100 characters or fewer.")
    if not message:
        errors.append("Please write a feedback message.")
    elif len(message) > 4000:
        errors.append("Your feedback must be 4000 characters or fewer.")
    if errors:
        return jsonify({"error": errors[0]}), 400
    try:
        database.save_feedback_submission(name, message)
    except Exception:
        logger.exception("Feedback submission could not be saved")
        return jsonify({"error": "We could not save your feedback. Please try again."}), 500
    return jsonify({"message": "Thank you for your feedback!"}), 201


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
    if request.path.startswith("/admin"):
        return render_template(
            "admin_dashboard.html",
            dashboard={
                "users_total": "—",
                "new_users": "—",
                "assessments_total": "—",
                "feedback_helpful_rate": "—",
                "status_counts": {},
                "days": [],
            },
            admin_error="An unexpected server error occurred while processing administrative data. Please check server logs.",
        ), 500
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
