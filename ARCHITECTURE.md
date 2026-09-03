# DiaBeates System Architecture

## Overview
DiaBeates is a Flask-based diabetes complication risk prediction system that combines rule-based scoring with machine learning models. The architecture follows a layered approach with clear separation of concerns.

## Architecture Diagram

```mermaid
graph TB
    subgraph Frontend["🖥️ Frontend Layer"]
        Home["home.html<br/>(Landing Page)"]
        Assessment["assessment.html<br/>(Input Form)"]
        Result["result.html<br/>(Risk Display)"]
        History["history.html<br/>(Session History)"]
        About["about.html<br/>(Documentation)"]
    end

    subgraph "🌐 Web Server"
        Flask["Flask Application<br/>(app.py)"]
    end

    subgraph "🧠 Business Logic Layer"
        Rules["Rule Matrix<br/>(rule_matrix.py)"]
        Recommendations["Recommendations<br/>(recommendations.py)"]
        Validation["Input Validation<br/>(validation.py)"]
        FieldLabels["Field Labels<br/>(field_labels.py)"]
    end

    subgraph "🤖 ML Layer"
        TrainModel["Model Training<br/>(train_model.py)"]
        ModelCache["Trained Models<br/>(model/ directory)"]
        Summary["Training Summary<br/>(training_summary.json)"]
    end

    subgraph "💾 Data Layer"
        Database["SQLite Database<br/>(database.py)"]
        DBAssessments["📊 assessments table"]
        DBResults["📊 risk_results table"]
        DBLabs["📊 lab_assessments table"]
        DBFeedback["📊 feedback table"]
    end

    subgraph "📁 Data Sources"
        TrainingData["Training Dataset<br/>(data/diabetes_dataset.csv)"]
        DataGen["Sample Data Generator<br/>(data/generate_sample_data.py)"]
    end

    subgraph "📦 Static Assets"
        Static["CSS, JS, Images<br/>(static/ directory)"]
    end

    %% Frontend to Flask
    Home --> Flask
    Assessment --> Flask
    Result --> Flask
    History --> Flask
    About --> Flask

    %% Flask to Business Logic
    Flask --> Validation
    Flask --> Rules
    Flask --> Recommendations
    Flask --> FieldLabels

    %% Flask to ML Layer
    Flask --> ModelCache

    %% Flask to Database
    Flask --> Database

    %% Database Schema
    Database --> DBAssessments
    Database --> DBResults
    Database --> DBLabs
    Database --> DBFeedback

    %% ML Training
    TrainingData --> TrainModel
    TrainModel --> ModelCache
    TrainModel --> Summary

    %% Rules use data schema
    Rules --> TrainModel

    %% Frontend Assets
    Static --> Home
    Static --> Assessment
    Static --> Result
    Static --> History

    %% Data Generation
    DataGen --> TrainingData

    style Frontend fill:#e1f5fe
    style Flask fill:#fff3e0
    style "🧠 Business Logic Layer" fill:#f3e5f5
    style "🤖 ML Layer" fill:#e8f5e9
    style "💾 Data Layer" fill:#fce4ec
    style "📁 Data Sources" fill:#ede7f6
```

## Component Description

### 1. **Frontend Layer** (Templates)
- **home.html** - Landing page with feature overview and CTA buttons
- **assessment.html** - Form for patient input (13 health indicators)
- **result.html** - Risk scores display (rule-based + ML model)
- **history.html** - Patient's session-specific assessment history
- **about.html** - Documentation and methodology
- **base.html** - Base template with navigation

### 2. **Web Server** (Flask)
- **app.py** - Main Flask application
  - Routes: `/`, `/assessment`, `/result`, `/history`, `/about`
  - Session management (anonymous session IDs)
  - Loads trained models at startup
  - Coordinates between frontend, business logic, and data layers

### 3. **Business Logic Layer**
- **rule_matrix.py (Version 2.0-clinical)**
  - Three guideline-aligned scoring engines: ACC/AHA 10-Yr ASCVD, KDIGO 2024 CKD Staging, and Michigan Neuropathy Screening Instrument (MNSI)
  - Converts risk factors to clinical risk tiers (Low ≤30%, Moderate 31-60%, High >60%)
  - Used exclusively for live, transparent clinical decision-support and interpretability (NOT for training label generation)
  
- **recommendations.py**
  - Converts risk tiers into plain-language guidance
  - Generates personalized wellness recommendations
  - Provides overall risk headline
  
- **validation.py**
  - Input validation for form submissions
  - Ensures data integrity before processing
  
- **field_labels.py**
  - Human-readable descriptions of patient indicators
  - Maps fields to display labels

### 4. **ML Layer**
- **clinical_data_pipeline.py**
  - Extracts confirmed diabetic cohorts from CDC NHANES and BRFSS registries
  - Establishes empirical clinical targets (physician-diagnosed heart disease and laboratory-confirmed KDIGO CKD)
  
- **train_model.py**
  - Trains calibrated classifiers on authentic clinical cohorts (breaking circular logic)
  - Evaluates discrimination (AUROC, PR-AUC), calibration (Brier score), and sensitivity
  - Outputs calibration curves and ROC analysis
  
- **clinical_model.py**
  - Encapsulates trained estimators in `ClinicalRiskWrapper` for reliable pickle serialization
  
- **model/** directory
  - Trained model files (per category)
  - training_summary.json - Best models, AUROC, Brier scores, and calibration metrics
  - clinical_roc_curves.png & clinical_calibration_curves.png

### 5. **Data Layer** (SQLite with WAL Mode)
- **database.py** - Database abstraction layer with safe, non-destructive migrations and Write-Ahead Logging
- **assessments** - Raw patient inputs + session_id + timestamp
- **risk_results** - Scored results (rule score, label, calibrated ML event probability, AUROC)
- **lab_assessments** - Optional lab values (HbA1c, Systolic BP, LDL)
- **feedback** - User feedback signals for model improvement

### 6. **Clinical Data Sources**
- **nhanes_2017_2018_heart_disease_prediction.csv** - CDC NHANES cardiovascular cohort (N=949)
- **CKD_NHANES_2021_2023.csv** - CDC NHANES nephropathy/CKD cohort (N=848)
- **diabetes_dataset.csv** - CDC BRFSS mobility/neuropathy cohort (N=35,346)

### 7. **Static Assets**
- CSS stylesheets (Tailwind-based)
- JavaScript for interactivity
- SVG icons and images

## Data Flow

### Assessment Submission Flow
```
User Input (assessment.html)
    ↓
Flask Route Handler (app.py)
    ↓
Input Validation (validation.py)
    ↓
Rule Matrix Scoring (rule_matrix.py)
    ↓
ML Model Prediction (trained models)
    ↓
Recommendations Generation (recommendations.py)
    ↓
Database Persistence (database.py → SQLite)
    ↓
Result Rendering (result.html)
```

### Model Training Flow
```
Clinical Cohorts (CDC NHANES 2017-2018, NHANES 2021-2023, BRFSS)
    ↓
clinical_data_pipeline.py (Cohort Extraction & Ground Truth Staging)
    ↓
train_model.py (5-Fold Stratified Cross-Validation on Train Partition)
    ↓
Model Selection via CV AUROC (Logistic Regression, Random Forest, Gradient Boosting)
    ↓
Final Evaluation on Untouched Holdout Test Set (AUROC, PR-AUC, Brier, Calibration)
    ↓
ClinicalRiskWrapper Serialization (joblib)
    ↓
model/ directory + training_summary.json (AUROC, 95% CI, Brier, Curves)
```

## Key Design Decisions

1. **Dual Decision Support** - Rule-based guideline scoring (ACC/AHA, KDIGO, MNSI) side-by-side with empirical ML risk forecasting
2. **Empirical Ground Truth** - Ground truth established from physician diagnoses and KDIGO lab staging, breaking circular rule distillation
3. **Calibrated Probabilities** - Calibrated event risk percentages ($P(\text{event}) \times 100$) rather than raw uncalibrated confidence
4. **Session Privacy** - Anonymous session IDs keep each user's history private
5. **Database Reliability** - SQLite Write-Ahead Logging (WAL) and non-destructive schema migrations

## Database Schema

| Table | Purpose |
|-------|---------|
| `assessments` | Raw inputs, session tracking, rule version |
| `risk_results` | Score outputs (rule + model) for each category |
| `lab_assessments` | Optional lab value tracking |
| `feedback` | User feedback for continuous improvement |

## Technology Stack

- **Backend**: Python 3, Flask
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Database**: SQLite
- **ML**: scikit-learn (trained classifiers), joblib (serialization)
- **Data**: pandas

