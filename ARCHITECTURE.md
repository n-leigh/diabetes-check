# DiaBeates System Architecture

## Overview
DiaBeates is a production-hardened, web-based clinical decision support system for diabetes complication triage. It combines evidence-based clinical guideline scoring with calibrated machine learning estimators across four microvascular and macrovascular complication domains. The architecture follows a modular, layered design with strict separation of concerns, containerized deployment, and robust security controls.

## Architecture Diagram

```mermaid
flowchart TB
  User((Patient or reviewer)) --> Browser[Web browser]

  subgraph UI[Presentation layer]
    Templates[Flask/Jinja templates<br/>home, assessment, result,<br/>history, print, about]
    Static[Static assets<br/>CSS, JavaScript, logo, media]
    Templates --- Static
  end
  Browser <--> Templates
  Browser -->|HTTP GET/POST| Runtime

  subgraph Runtime[Production runtime]
    Container[Docker container<br/>python:3.11-slim, non-root appuser]
    WSGI[Waitress WSGI<br/>wsgi.py, 8 threads]
    App[Flask application<br/>app.py]
    Health[/health probe/]
    Container --> WSGI --> App
    App --> Health
  end

  subgraph Controls[Request controls]
    Session[Anonymous session ID<br/>HttpOnly, SameSite cookie]
    CSRF[CSRF protection<br/>Flask-WTF]
    RateLimit[IP rate limiting<br/>Flask-Limiter]
    Headers[Security response headers<br/>CSP-related browser controls]
  end
  App --> Session
  App --> CSRF
  App --> RateLimit
  App --> Headers

  subgraph Assessment[Assessment processing]
    Validate[validation.py<br/>bounds and required fields]
    RuleEngine[rule_matrix.py<br/>4 guideline-aligned domains<br/>plus optional lab scoring]
    MLInference[clinical_model.py<br/>4 loaded calibrated classifiers]
    Explain[recommendations.py<br/>risk drivers and guidance]
    Labels[field_labels.py<br/>human-readable patient fields]
    Validate --> RuleEngine
    Validate --> MLInference
    RuleEngine --> Explain
    RuleEngine --> Labels
    MLInference --> Explain
  end
  App --> Validate
  Explain --> App
  Labels --> App
  App --> Templates

  subgraph Domains[Clinical risk domains]
    CVD[Cardiovascular<br/>ACC/AHA and UKPDS]
    CKD[Nephropathy / CKD<br/>KDIGO 2024]
    Neuro[Neuropathy / mobility<br/>MNSI-aligned]
    Retina[Retinopathy / vision<br/>ADA and AAO-aligned]
    RuleEngine --> CVD
    RuleEngine --> CKD
    RuleEngine --> Neuro
    RuleEngine --> Retina
    MLInference --> CVD
    MLInference --> CKD
    MLInference --> Neuro
    MLInference --> Retina
  end

  subgraph Storage[Local persistence]
    DBAPI[database.py<br/>SQLite, WAL mode, foreign keys]
    Assessments[(assessments<br/>inputs, session, timestamps)]
    Results[(risk_results<br/>rule + model outputs)]
    Labs[(lab_assessments<br/>HbA1c, BP, LDL)]
    Feedback[(feedback<br/>helpfulness signal)]
    Retention[Archive, delete,<br/>and retention utilities]
    DBAPI --> Assessments
    DBAPI --> Results
    DBAPI --> Labs
    DBAPI --> Feedback
    DBAPI --> Retention
  end
  App <--> DBAPI
  Assessment --> DBAPI
  Storage --> Templates

  subgraph Training[Offline training and model release]
    Sources[CDC NHANES and BRFSS<br/>cohort source files]
    Pipeline[clinical_data_pipeline.py<br/>cohort extraction and normalization]
    Trainer[train_model.py<br/>split, 5-fold CV, calibration,<br/>metrics and bootstrap CIs]
    Wrapper[ClinicalRiskWrapper<br/>feature selection and risk tiers]
    Artifacts[model/*.pkl<br/>training_summary.json<br/>ROC and calibration plots]
    Sources --> Pipeline --> Trainer --> Wrapper --> Artifacts
  end
  Artifacts -->|loaded at app startup| MLInference

  classDef runtime fill:#fff3e0,stroke:#d97706,color:#1f2937
  classDef control fill:#fef3c7,stroke:#b45309,color:#1f2937
  classDef clinical fill:#e8f5e9,stroke:#2e7d32,color:#1f2937
  classDef data fill:#fce4ec,stroke:#ad1457,color:#1f2937
  classDef ui fill:#e1f5fe,stroke:#0277bd,color:#1f2937
  class Container,WSGI,App,Health runtime
  class Session,CSRF,RateLimit,Headers control
  class Validate,RuleEngine,MLInference,Explain,Labels,CVD,CKD,Neuro,Retina clinical
  class DBAPI,Assessments,Results,Labs,Feedback,Retention,Sources,Pipeline,Trainer,Wrapper,Artifacts data
  class User,Browser,Templates,Static ui
```

## Component Description

### 1. **Frontend Layer** (Templates & Modals)
- **home.html** - Landing page with system overview, complication cards, and clinical CTA pathways.
- **assessment.html** - Patient input form featuring 15 non-invasive clinical indicators, optional point-of-care laboratory biomarkers, and an accessible, interactive BMI calculator modal with unit conversion.
- **result.html** - Comprehensive 4-domain risk presentation combining clinical guideline tiers with calibrated empirical ML probabilities, alongside patient-specific risk driver explanations.
- **history.html** - Longitudinal patient assessment history supporting sortable chronological order (newest/oldest), stable sequential record numbering (`#1`, `#2`, ...), localized Philippine Standard Time (PHT / UTC+8) timestamps, soft archiving, and accessible deletion confirmation modals.
- **print_result.html** - Dedicated print-optimized PDF summary formatted specifically for clinical charts with coded factor translations and medical disclaimers.
- **about.html** - Clinical methodology, cohort provenance, algorithmic architecture, and ethical scope.
- **base.html** - Base layout providing WCAG-compliant navigation, semantic landmark regions, accessible skip links, and alert banners.

### 2. **Deployment & Web Server Layer**
- **Dockerfile & docker-compose.yml**
  - Production containerization running on `python:3.11-slim` under an unprivileged `appuser`.
  - Built-in Docker health check targeting `/health`.
  - Persistent volume mounts for SQLite database and rotating log files.
- **wsgi.py**
  - Multi-threaded production WSGI entrypoint powered by Waitress (`threads=8`, configurable host/port).
- **app.py**
  - Main Flask application with route handlers: `/`, `/assessment`, `/predict`, `/history`, `/history/<id>/print`, `/history/<id>/archive`, `/history/<id>/delete`, `/about`, and `/health`.
  - Enforces Flask-WTF CSRF protection across all modifying endpoints.
  - Applies strict HTTP security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, and `Strict-Transport-Security` in production).
  - Enforces IP-based rate limiting via Flask-Limiter (`300 per day`, `100 per hour`).
  - Implements operational `/health` probe verifying database connectivity and model status.

### 3. **Business Logic Layer**
- **rule_matrix.py (Version 2.0-clinical)**
  - Four evidence-based guideline scoring engines:
    1. **Cardiovascular**: ACC/AHA 10-Yr ASCVD & UKPDS risk factor scoring.
    2. **Nephropathy**: KDIGO 2024 Chronic Kidney Disease risk staging.
    3. **Neuropathy**: Michigan Neuropathy Screening Instrument (MNSI) functional mobility mapping.
    4. **Retinopathy**: American Diabetes Association (ADA) and American Academy of Ophthalmology (AAO) screening criteria.
  - Converts risk factors to clinical risk tiers: Low ($\le 30\%$), Moderate ($31\% - 60\%$), High ($> 60\%$).
  - Serves exclusively as an interpretable baseline and explanation layer (never used to generate training labels).
- **recommendations.py**
  - Generates personalized lifestyle, surveillance, and specialist referral recommendations.
  - Computes patient-specific risk drivers to explain the exact clinical factors contributing to elevated risk.
- **validation.py**
  - Server-side bounds checking for all 15 clinical indicators and optional laboratory values.
  - Guarantees data integrity prior to rule execution, inference, or persistence.
- **field_labels.py**
  - Human-readable descriptions, units, and categorized labels for patient indicators.

### 4. **Machine Learning Layer**
- **clinical_data_pipeline.py**
  - Ingests authentic epidemiological data from CDC NHANES (CVD, CKD, Retinopathy) and CDC BRFSS.
  - Preprocesses clinical features and encodes gold-standard empirical diagnostic endpoints.
- **train_model.py**
  - Trains calibrated machine learning models using 5-fold Stratified Cross-Validation strictly within training partitions.
  - Evaluates candidate models (Calibrated Logistic Regression, Calibrated Random Forest, Gradient Boosting).
  - Derives leak-free operating thresholds using Youden's J statistic targeting high sensitivity (>86%) and NPV (>79%–96%).
  - Computes 95% bootstrap confidence intervals (1,000 resamples) for all discrimination and calibration metrics.
- **clinical_model.py**
  - Encapsulates winning estimators in `ClinicalRiskWrapper` to guarantee deterministic, environment-agnostic joblib serialization.
- **model/ Directory**
  - `cardiovascular_model.pkl`: Calibrated ASCVD risk estimator.
  - `general_burden_model.pkl`: Calibrated KDIGO CKD risk estimator.
  - `neuropathy_mobility_model.pkl`: Calibrated MNSI mobility risk estimator.
  - `retinopathy_model.pkl`: Calibrated Retinopathy risk estimator.
  - `training_summary.json`: Detailed epidemiological validation metrics, thresholds, and bootstrap CIs.
  - `clinical_roc_curves.png` & `clinical_calibration_curves.png`: Diagnostic discrimination and calibration plots.

### 5. **Data Persistence Layer** (SQLite with WAL Mode)
- **database.py** - Database abstraction layer featuring non-destructive schema migrations and Write-Ahead Logging.
  - `assessments` - Raw clinical indicators, diabetes duration, blurry vision, session ID, archive flag, and UTC timestamp.
  - `risk_results` - Rule-based scores, guideline labels, calibrated ML event probabilities, and AUROC metrics across all 4 domains.
  - `lab_assessments` - Optional laboratory biomarkers (HbA1c, Systolic BP, LDL).
  - `feedback` - User feedback for continuous quality monitoring.
  - `prune_expired_assessments()` - Automated data retention policy pruning assessments older than 90 days.

### 6. **Authentic Clinical Data Sources**
- `nhanes_2017_2018_heart_disease_prediction.csv` - CDC NHANES 2017–2018 CVD diabetic cohort ($N=949$).
- `CKD_NHANES_2021_2023.csv` - CDC NHANES 2021–2023 nephropathy cohort with laboratory eGFR/uACR ($N=848$).
- `diabetes_dataset.csv` - CDC BRFSS diabetic registry ($N=35,346$ population, $N=5,000$ stratified sample).
- `processed_retinopathy_cohort.csv` - CDC NHANES Retinopathy Exam cohort with digital retinal imaging ($N=797$).

---

## Data Flow Pipelines

### 1. Assessment Submission Flow
```
Patient Form Submission (assessment.html)
    ↓
Flask Route Handler (/predict in app.py)
    ↓
CSRF & Rate Limit Verification (Flask-WTF + Flask-Limiter)
    ↓
Server-Side Input Validation (validation.py)
    ↓
Guideline Rule Matrix Scoring (rule_matrix.py: 4 Domains)
    ↓
Calibrated ML Model Inference (model/*.pkl via ClinicalRiskWrapper)
    ↓
Patient-Specific Risk Drivers & Recommendations (recommendations.py)
    ↓
Database Persistence (database.py → SQLite WAL)
    ↓
Presentation Rendering (result.html / print_result.html)
```

### 2. Clinical Training & Evaluation Flow
```
Epidemiological Cohorts (CDC NHANES CVD, CKD, Retinopathy & BRFSS)
    ↓
clinical_data_pipeline.py (Cohort Extraction & Ground Truth Encoding)
    ↓
Stratified 80/20 Train/Test Partitioning
    ↓
5-Fold Stratified Cross-Validation on Training Folds Only
    ↓
Model Comparison (Calibrated Logistic Regression vs Random Forest vs Gradient Boosting)
    ↓
Platt / Isotonic Calibration (CalibratedClassifierCV)
    ↓
Leak-Free Threshold Selection on Training Folds via Youden's J
    ↓
Holdout Test Evaluation with 95% Bootstrap Confidence Intervals (1,000 Resamples)
    ↓
Serialization via ClinicalRiskWrapper into model/*.pkl
```

---

## Technology Stack

- **Server Runtime**: Python 3.11, Waitress WSGI, Docker, Docker Compose
- **Web Framework**: Flask 3.0+, Flask-WTF (CSRF), Flask-Limiter, python-dotenv
- **Machine Learning**: scikit-learn 1.4+, joblib, pandas, numpy, matplotlib
- **Database**: SQLite3 (Write-Ahead Logging mode)
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript (WCAG 2.1 AA compliant)

