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
import uuid
import secrets
import logging
import logging.handlers
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import joblib
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
        with open(secret_key_path, "x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    with open(secret_key_path, encoding="utf-8") as secret_file:
        SECRET_KEY = secret_file.read().strip()
DEBUG = os.getenv("DEBUG", "False").strip().lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").strip().lower() in {"1", "true", "yes", "on"}
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
    SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=86400,
)
csrf = CSRFProtect(app)


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
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if not DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["300 per day", "100 per hour"],
    storage_uri="memory://",
)

database.init_db()
logger.info("Database initialized successfully with non-destructive WAL mode.")
try:
    RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))
except ValueError:
    RETENTION_DAYS = 90
pruned_count = database.prune_expired_assessments(days=RETENTION_DAYS)
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
            MODELS[cat] = joblib.load(path)
        except Exception as e:
            logger.error(f"Error loading model for {cat}: {e}")
    else:
        logger.warning(f"Model file not found for '{cat}' at {path}")


@app.before_request
def ensure_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session.permanent = True


@app.after_request
def add_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' data: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'self'; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    return response


@app.route("/", methods=["GET"])
def index():
    return render_template("home.html")


@app.route("/assessment", methods=["GET"])
def assessment():
    return render_template("assessment.html")


@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


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
    if MODELS:
        X = pd.DataFrame([patient])[FEATURE_COLUMNS]
        for cat in CATEGORIES:
            if cat in MODELS:
                model = MODELS[cat]
                pred = model.predict(X)[0]
                model_results[cat] = pred
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(X)[0]
                    risk_pct = round(proba[1] * 100, 1) if len(proba) == 2 else round(max(proba) * 100, 1)
                    model_confidences[cat] = risk_pct

    assessment_id = database.save_assessment(
        session_id=session["session_id"],
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
    )


@app.route("/history", methods=["GET"])
def history():
    show_archived = request.args.get("view") == "archived"
    sort_order = request.args.get("sort", "desc").lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    # Always fetch in asc order first to establish baseline chronological numbering (1, 2, 3...)
    asc_records = database.get_all_assessments(session_id=session["session_id"], archived=show_archived, sort_order="asc")
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
    database.set_archived(assessment_id, session_id=session["session_id"], archived=archived)
    return redirect(url_for("history", view="archived" if came_from_archived else None))


@app.route("/history/<int:assessment_id>/delete", methods=["POST"])
def delete_assessment(assessment_id):
    came_from_archived = request.form.get("from") == "archived"
    database.delete_assessment(assessment_id, session_id=session["session_id"])
    return redirect(url_for("history", view="archived" if came_from_archived else None))


@app.route("/history/<int:assessment_id>", methods=["GET"])
def history_detail(assessment_id):
    record = database.get_assessment(assessment_id, session_id=session["session_id"])
    if not record:
        return redirect(url_for("history"))
    patient_drivers = explain_patient_risk(record["patient"])
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
        recommendations=build_recommendations(record["rule_results"], record.get("lab_assessment")),
        patient_drivers=patient_drivers,
        viewing_past=True,
        created_at=record["created_at"],
        assessment_id=assessment_id,
    )


@app.route("/history/<int:assessment_id>/print", methods=["GET"])
def print_result(assessment_id):
    record = database.get_assessment(assessment_id, session_id=session["session_id"])
    if not record:
        return redirect(url_for("history"))
    patient_drivers = explain_patient_risk(record["patient"])
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
    )


@app.route("/feedback/<int:assessment_id>", methods=["POST"])
def feedback(assessment_id):
    record = database.get_assessment(assessment_id, session_id=session["session_id"])
    if not record:
        return redirect(url_for("history"))

    helpful = request.form.get("helpful") == "yes"
    database.save_feedback(assessment_id, helpful)
    return redirect(url_for("history_detail", assessment_id=assessment_id) + "?feedback=thanks")


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
    logger.exception("Unexpected server error")
    return render_template(
        "assessment.html",
        errors=["An error occurred while processing your assessment. Please check your inputs and try again."],
        form_data={},
    ), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=DEBUG)
