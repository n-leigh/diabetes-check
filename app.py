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
import logging
import logging.handlers
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

DEFAULT_SECRET_KEY = "diabeates-dev-secret-replace-before-any-real-deployment"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
DEBUG = os.getenv("DEBUG", "False").strip().lower() in {"1", "true", "yes", "on"}

if SECRET_KEY == DEFAULT_SECRET_KEY:
    logger.warning("SECURITY WARNING: Using default secret key. Set SECRET_KEY in .env for production.")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["TEMPLATES_AUTO_RELOAD"] = True
csrf = CSRFProtect(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["300 per day", "100 per hour"],
    storage_uri="memory://",
)

database.init_db()
logger.info("Database initialized successfully with non-destructive WAL mode.")

CATEGORIES = ["cardiovascular", "neuropathy_mobility", "general_burden"]
FEATURE_COLUMNS = [
    "HighBP", "HighChol", "Smoker", "HeartDiseaseorAttack", "Stroke",
    "BMI", "Age", "DiffWalk", "PhysHlth", "GenHlth", "MentHlth",
    "NoDocbcCost", "Sex",
]

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


@app.route("/", methods=["GET"])
def index():
    return render_template("home.html")


@app.route("/assessment", methods=["GET"])
def assessment():
    return render_template("assessment.html")


@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


@app.route("/predict", methods=["POST"])
@limiter.limit("20 per minute")
def predict():
    patient, lab_values, errors = validate_patient_form(request.form)

    if errors:
        return render_template(
            "assessment.html",
            errors=errors,
            form_data=request.form,
        ), 400

    rule_results = compute_all_risks(patient)

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
        assessment_id=assessment_id,
    )


@app.route("/history", methods=["GET"])
def history():
    show_archived = request.args.get("view") == "archived"
    records = database.get_all_assessments(session_id=session["session_id"], archived=show_archived)
    return render_template("history.html", records=records, categories=CATEGORIES, show_archived=show_archived)


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
        viewing_past=True,
        created_at=record["created_at"],
        assessment_id=assessment_id,
    )


@app.route("/history/<int:assessment_id>/print", methods=["GET"])
def print_result(assessment_id):
    record = database.get_assessment(assessment_id, session_id=session["session_id"])
    if not record:
        return redirect(url_for("history"))
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
    logger.exception(f"Unexpected server error: {e}")
    return render_template(
        "assessment.html",
        errors=["An error occurred while processing your assessment. Please check your inputs and try again."],
        form_data={},
    ), 500


if __name__ == "__main__":
    app.run(debug=DEBUG)