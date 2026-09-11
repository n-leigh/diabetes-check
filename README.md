# Web-Based Diabetes Complication Prediction System (DiaBeates)

Clinical guideline rule matrix + calibrated machine learning risk estimators + production-ready Flask web application, trained and evaluated on authentic epidemiological cohorts from the CDC National Health and Nutrition Examination Survey (NHANES) and the CDC Behavioral Risk Factor Surveillance System (BRFSS).

---

## Disclaimer / Ethical Scope
> "This tool estimates complication risk using statistical models trained on population health data. The result is intended for screening and education, not diagnosis. A higher result may justify discussing follow-up testing with a healthcare professional. A lower result does not rule out disease."

---

## Overview

DiaBeates provides dual-tiered clinical decision support for diabetes complication triage across four major microvascular and macrovascular complication domains:

1. **Cardiovascular Disease (ASCVD)**: Evaluates coronary heart disease, angina pectoris, and myocardial infarction risk trained on the CDC NHANES 2017–2018 diabetic cohort ($N=949$). Aligned with ACC/AHA ASCVD & UKPDS clinical guidelines.
2. **Nephropathy & Chronic Kidney Disease (KDIGO)**: Predicts laboratory-confirmed CKD (eGFR $< 60\text{ mL/min/1.73m}^2$ via CKD-EPI 2021 or pathological albuminuria $\text{uACR} \ge 30\text{ mg/g}$) trained on the CDC NHANES 2021–2023 cohort ($N=848$). Aligned with KDIGO 2024 staging guidelines.
3. **Neuropathy & Functional Mobility (MNSI)**: Predicts lower-extremity mobility impairment and peripheral neuropathy proxy (`DiffWalk`) trained on the CDC BRFSS diabetic registry ($N=5,000$ stratified sample). Aligned with Michigan Neuropathy Screening Instrument (MNSI).
4. **Diabetic Retinopathy & Vision Loss (ADA / AAO)**: Evaluates microvascular retinal disease and vision impairment trained on the CDC NHANES Retinopathy Examination cohort ($N=797$). Aligned with American Diabetes Association (ADA) and American Academy of Ophthalmology (AAO) screening guidelines.

---

## Empirical Clinical Performance

All models are evaluated on untouched holdout test sets using 5-fold cross-validation with 95% bootstrap confidence intervals (1,000 resamples). The system implements a **dual-threshold approach** (Screening and Referral thresholds) derived strictly within training folds from out-of-fold predictions to guide clinical decision tiers:

| Complication Domain | Winning Classifier | AUROC [95% CI] | ECE | Brier Score | Screening Thresh | Referral Thresh | Status |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Cardiovascular (ASCVD)** | Logistic Regression | **0.7644** [0.685–0.836] | 0.052 | **0.1549** | TBD | TBD | Validated |
| **Nephropathy & Renal (KDIGO)** | Logistic Regression | **0.7630** [0.690–0.837] | 0.048 | **0.1966** | TBD | TBD | Validated |
| **Neuropathy & Mobility (MNSI)** | Gradient Boosting | **0.7992** [0.771–0.826] | 0.061 | **0.1765** | TBD | TBD | Validated |
| **Retinopathy & Vision (ADA)** | Logistic Regression | **0.6421** [0.547–0.723] | 0.120 | **0.2366** | TBD | TBD | **Experimental** |

*Full epidemiological comparison across algorithms, out-of-fold calibration curves, and feature importances are recorded in [`model/training_summary.json`](model/training_summary.json) and detailed in [`METHODOLOGY.md`](METHODOLOGY.md).*

---

## Key Architectural Principles & Features

1. **Empirical Ground Truth (No Circular Logic)**: Classifiers are trained directly on authentic clinical and laboratory endpoints (physician diagnoses, KDIGO lab staging, digital retinal exams, and validated functional impairment), completely eliminating circular rule distillation.
2. **Dual-Threshold Decision Support**: Transparent, guideline-based risk tiers (ACC/AHA ASCVD, KDIGO 2024, MNSI, ADA Retinopathy) are combined with a **dual-threshold system (Screening and Referral thresholds)** applied to calibrated empirical probabilities to guide clinical action accurately.
3. **Patient-Specific Risk Drivers**: Dynamic risk explanation engine identifies the primary clinical factors contributing to elevated risk for each individual patient in both the result view and printable chart.
4. **Two-Tiered Screening Architecture**:
   - **Tier 1 (Non-Invasive)**: 15 clinical indicators (demographics, vitals, lifestyle, symptoms, diabetes duration, vision changes) completed in under 2 minutes without laboratory requisitions.
   - **Tier 2 (Point-of-Care Biomarkers)**: Optional HbA1c, Systolic BP, and LDL cholesterol scored against ADA 2026 clinical targets.
5. **Interactive Health Utilities**: Accessible, modal-based interactive BMI calculator with unit conversion (metric and imperial) integrated directly into the assessment workflow.
6. **Assessment History & Longitudinal Tracking**:
   - Sortable chronological views (toggle between newest and oldest records).
   - Stable sequential assessment numbering (`#1`, `#2`, `#3`, ...).
   - Localized Philippine Standard Time (PHT / UTC+8) display formatting.
   - Soft archiving and confirmation-gated permanent deletion with accessible focus trapping.
7. **Printable Clinical Summary**: Dedicated `/history/<id>/print` endpoint with clean print CSS, coded value translations, risk driver breakdowns, and clinical disclaimers for patient medical records.
8. **Production Hardening & Reliability**:
   - Multi-stage containerization with Docker and Docker Compose running as an unprivileged user.
   - Multi-threaded production WSGI server via Waitress (`wsgi.py`).
   - Container health check probe via `/health` (verifying database connectivity and loaded models).
   - SQLite Write-Ahead Logging (WAL mode) with safe schema migrations and automatic data retention pruning.
   - Enterprise security controls: Flask-WTF CSRF protection, secure session cookies (HttpOnly, SameSite, Secure in production), and defensive HTTP security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS).

---

## Project Structure

```
diabetes-check/
├── Dockerfile                  # Container build specification (Python 3.11-slim, non-root user, healthcheck)
├── docker-compose.yml          # Container orchestration with volume persistence and health probes
├── wsgi.py                     # Production WSGI server entrypoint powered by Waitress
├── app.py                      # Flask application (sessions, CSRF, security headers, routing, /health)
├── rule_matrix.py              # Clinical guideline rule engines (ACC/AHA ASCVD, KDIGO, MNSI, ADA Retinopathy)
├── clinical_data_pipeline.py   # Cohort extraction and ground-truth preprocessing (NHANES & BRFSS)
├── train_model.py              # 5-fold cross-validation, Platt calibration, training-fold threshold selection
├── clinical_model.py           # ClinicalRiskWrapper for reliable scikit-learn model serialization
├── database.py                 # SQLite persistence with WAL mode, safe migrations, and data pruning
├── validation.py               # Strict server-side input bounds checking
├── recommendations.py          # Clinical recommendations and patient-specific risk driver explanations
├── field_labels.py             # Human-readable field label mappings and formatted values
├── requirements.txt            # Python dependencies
├── test_clinical_system.py     # End-to-end automated clinical, accessibility, and security test suite
├── test_both_flows.py          # Dual flow verification script
├── live_browser_test.py        # Browser automation test helper
├── data/
│   ├── nhanes_2017_2018_heart_disease_prediction.csv  # CDC NHANES 2017-2018 CVD cohort (N=949)
│   ├── CKD_NHANES_2021_2023.csv                       # CDC NHANES 2021-2023 CKD cohort (N=848)
│   ├── diabetes_dataset.csv                           # CDC BRFSS diabetic registry (N=35,346)
│   └── processed_retinopathy_cohort.csv               # CDC NHANES Retinopathy cohort (N=797)
├── model/
│   ├── cardiovascular_model.pkl       # Calibrated ASCVD risk estimator
│   ├── general_burden_model.pkl       # Calibrated KDIGO CKD risk estimator
│   ├── neuropathy_mobility_model.pkl  # Calibrated MNSI mobility risk estimator
│   ├── retinopathy_model.pkl          # Calibrated Retinopathy risk estimator
│   ├── training_summary.json          # Epidemiological metrics, 95% bootstrap CIs, and thresholds
│   ├── clinical_roc_curves.png        # Out-of-fold ROC curves
│   └── clinical_calibration_curves.png# Brier score calibration plots
├── templates/
│   ├── base.html            # Core layout with navigation, accessible structure, and alert banners
│   ├── home.html            # System landing page and overview
│   ├── assessment.html      # 15 clinical indicators + optional lab values + interactive BMI calculator
│   ├── result.html          # 4-domain risk presentation, guideline tiers, and patient-specific risk drivers
│   ├── history.html         # Longitudinal assessment table (sortable, stable IDs, PHT time, archive/delete)
│   ├── print_result.html    # Print-optimized PDF clinical summary for charts
│   └── about.html           # Clinical methodology, data provenance, and ethical scope
└── logs/                    # Rotating application logs (10MB rotation, 5 backups)
```

---

## How to Run

### Option 1: Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run automated test suite
python test_clinical_system.py

# 3. Start development server
python app.py
# Access http://127.0.0.1:5000
```

### Option 2: Production WSGI Server (Waitress)

```bash
# Run production multi-threaded server on port 5000
python wsgi.py
```

### Option 3: Docker & Docker Compose

```bash
# Build and run containerized service in background
docker compose up --build -d

# Check service logs
docker compose logs -f

# Check container health status
docker compose ps

# Stop service
docker compose down
```

### Operational Health Check

The service exposes an automated health probe at `/health`:

```bash
curl http://127.0.0.1:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "models_loaded": [
    "cardiovascular",
    "general_burden",
    "neuropathy_mobility",
    "retinopathy"
  ]
}
```

---

## Automated Verification Suite

To verify rule calculations, database migrations, endpoint responses, CSRF enforcement, accessibility attributes, security headers, and data pruning:

```bash
python test_clinical_system.py
```

---

## Clinical Documentation

- [`METHODOLOGY.md`](METHODOLOGY.md): In-depth clinical epidemiology, data cohort provenance, cross-validation methodology, threshold selection, and limitations.
- [`DEFENSE_QUICK_START.md`](DEFENSE_QUICK_START.md): Defense presentation notes, architectural justifications, and key answers for thesis or project panels.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): System architecture diagrams, component interactions, and data flow pipelines.
- [`SECURITY.md`](SECURITY.md): Security architecture, threat modeling, CSRF/XSS mitigations, and compliance safeguards.