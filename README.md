# Web-Based Diabetes Complication Prediction System (DiaBeates)

Clinical guideline rule matrix (v2.0-clinical) + calibrated machine learning risk estimators + Flask web app, trained and evaluated on authentic epidemiological cohorts from the CDC National Health and Nutrition Examination Survey (NHANES) and the CDC Behavioral Risk Factor Surveillance System (BRFSS).

## Overview

DiaBeates provides dual-tiered clinical decision support for diabetes complication triage:
1. **Cardiovascular Disease (ASCVD)**: Evaluates coronary heart disease, angina, and myocardial infarction risk trained on the CDC NHANES 2017–2018 diabetic cohort ($N=949$).
2. **Nephropathy & Chronic Kidney Disease (KDIGO)**: Predicts laboratory-confirmed CKD (eGFR $< 60\text{ mL/min/1.73m}^2$ or pathological albuminuria $\text{uACR} \ge 30\text{ mg/g}$) trained on the CDC NHANES 2021–2023 cohort ($N=848$).
3. **Neuropathy & Functional Mobility (MNSI)**: Predicts lower-extremity mobility impairment and peripheral neuropathy proxy (`DiffWalk`) trained on the CDC BRFSS diabetic registry ($N=5,000$ stratified sample).

## Setup

```bash
pip install -r requirements.txt
```

## Project Structure

```
app.py                     # Flask web app (session management, CSRF protection, /history, /predict)
rule_matrix.py             # Clinical guideline rule matrix (ACC/AHA ASCVD, KDIGO, MNSI)
clinical_data_pipeline.py  # Cohort extraction & ground truth preprocessing (NHANES & BRFSS)
train_model.py             # 5-fold CV, calibration, training-fold threshold selection, bootstrap CIs
clinical_model.py          # ClinicalRiskWrapper for reliable model serialization
database.py                 # SQLite persistence with Write-Ahead Logging (WAL) & safe migrations
validation.py              # Strict server-side input bounds checking
recommendations.py         # Clinical tier guidance and lifestyle recommendations
data/
  nhanes_2017_2018_heart_disease_prediction.csv  # CDC NHANES 2017-2018 CVD cohort (N=949)
  CKD_NHANES_2021_2023.csv                       # CDC NHANES 2021-2023 CKD cohort (N=848)
  diabetes_dataset.csv                           # CDC BRFSS diabetic registry (N=35,346)
templates/
  home.html                # Landing page
  assessment.html          # Patient input form (13 health indicators + optional lab values)
  result.html              # Dual risk result display (guideline tier + calibrated ML risk)
  history.html             # Patient session assessment history
  print_result.html        # Print-optimized PDF clinical summary
  about.html               # Clinical methodology & ethical scope
model/
  cardiovascular_model.pkl       # Calibrated ASCVD risk model
  general_burden_model.pkl       # Calibrated KDIGO CKD risk model
  neuropathy_mobility_model.pkl  # Calibrated MNSI mobility risk model
  training_summary.json          # Epidemiological validation metrics & 95% bootstrap CIs
  clinical_roc_curves.png        # Out-of-fold ROC curves
  clinical_calibration_curves.png# Brier score calibration plots
```

## How to Run

```bash
# 1. (Optional) Retrain models and re-evaluate on clinical cohorts
python train_model.py

# 2. Run automated verification tests
python test_clinical_system.py

# 3. Start the Flask application
python app.py
# Open http://127.0.0.1:5000
```

## Empirical Clinical Performance

All models are evaluated on untouched holdout test sets with 95% bootstrap confidence intervals (1,000 resamples):

| Complication Domain | Winning Classifier | AUROC [95% CI] | PR-AUC | Brier Score | Sensitivity | NPV |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Cardiovascular (ASCVD)** | Calibrated Logistic Regression | **0.7644** [0.685–0.836] | 0.4700 | **0.1549** | **93.33%** | **95.59%** |
| **Nephropathy & Renal (KDIGO)** | Calibrated Logistic Regression | **0.7630** [0.690–0.837] | 0.8689 | **0.1966** | **86.24%** | **63.41%** |
| **Neuropathy & Mobility (MNSI)** | Gradient Boosting Classifier | **0.7992** [0.771–0.826] | 0.6823 | **0.1765** | **87.26%** | **88.56%** |

Full epidemiological comparison across algorithms and folds is recorded in [`model/training_summary.json`](model/training_summary.json) and detailed in [`METHODOLOGY.md`](METHODOLOGY.md).

## Key Architectural Principles

1. **Empirical Ground Truth**: Models break circular rule distillation by learning from physician diagnoses and laboratory-confirmed clinical endpoints.
2. **Dual Decision Support**: Guideline-based scores (ACC/AHA ASCVD, KDIGO, MNSI) provide transparent interpretability alongside data-driven calibrated probabilities.
3. **Leak-Free Thresholds**: Decision thresholds are derived strictly within training folds using Youden's J statistic, optimizing for high sensitivity (>86%) and NPV (>88–96%) for triage safety.
4. **Two-Tiered Screening**:
   - Tier 1: 13 non-invasive clinical indicators (lifestyle, vitals, symptoms) accessible in under 2 minutes.
   - Tier 2: Optional point-of-care laboratory biomarkers (HbA1c, Systolic BP, LDL) scored against ADA 2026 guidelines.
5. **Production Hardening**: Flask-WTF CSRF protection, SQLite Write-Ahead Logging (WAL) with safe migrations, rotating logging (10MB rotation, 5 backups), and strict server-side validation.

## Printable Clinical Summary

Every assessment offers a "Print / Save Result" action linking to `/history/<id>/print` — a dedicated template ([`templates/print_result.html`](templates/print_result.html)) with print styling, coded value translation, and clinical disclaimers for patient charts.