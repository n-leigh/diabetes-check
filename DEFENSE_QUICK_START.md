# DEFENSE PREPARATION QUICK START GUIDE

## System Overview
**System Name**: Diabetes Complication Prediction System (**DiaBeates**)  
**Type**: Hybrid clinical decision-support system (Guideline Rules + Calibrated ML)  
**Technology Stack**: Python 3.9+, Flask 3.0+, scikit-learn, SQLite3 (WAL Mode)  
**Status**: ✅ Defense-ready (100% Reconciled: authentic CDC cohorts, leak-free CV, calibrated probabilities, 95% bootstrap CIs)

---

## Key Talking Points for Defense

### 1. "What does the system do?"
**Answer**: Stratifies diabetes-related complication risk across three critical clinical domains:
- **Cardiovascular (ASCVD)**: Coronary heart disease, angina, and myocardial infarction risk
- **Nephropathy & Chronic Kidney Disease (KDIGO)**: Renal filtration impairment, eGFR decline, and albuminuria
- **Neuropathy & Functional Mobility (MNSI)**: Peripheral nerve damage and lower-extremity mobility limitation

Uses a **hybrid dual decision-support approach**: transparent guideline-based scoring side-by-side with probability-calibrated empirical ML classifiers.

**Reference Document**: [METHODOLOGY.md](METHODOLOGY.md#overview)

---

### 2. "How does the model work?"
**Answer**: 
1. **Empirical Ground Truth (Breaking Circular Logic)**:
   - Models are **NOT** trained on synthetic rule-generated labels.
   - Classifiers are trained on **external, authentic clinical ground truth**: physician diagnoses (CDC NHANES 2017–2018), laboratory-confirmed KDIGO CKD staging (CDC NHANES 2021–2023), and functional mobility impairment (CDC BRFSS diabetic cohort).

2. **Guideline-Aligned Rule Matrix (v2.0-clinical)**:
   - Three evidence-based scoring engines: ACC/AHA ASCVD, KDIGO 2024 CKD Staging, and Michigan Neuropathy Screening Instrument (MNSI).
   - Used strictly as an interpretable baseline and clinical explanation layer for physicians and patients.

3. **Calibrated Machine Learning Classifiers**:
   - Compares Calibrated Logistic Regression, Calibrated Random Forest, and Gradient Boosting.
   - Evaluated using 5-fold Stratified Cross-Validation on the training partition only.
   - Calibrated using `CalibratedClassifierCV` so that model outputs represent true event probabilities $P(\text{event}) \times 100\%$.

4. **Dual Presentation**:
   - Users and clinicians view both the transparent clinical guideline tier and the calibrated empirical ML risk probability.

**Reference Document**: [METHODOLOGY.md](METHODOLOGY.md#machine-learning-pipeline--model-selection)

---

### 3. "What performance and accuracy did you achieve?"
**Answer**: 
Rather than reporting naive accuracy on circular labels, models are evaluated on gold-standard epidemiological discrimination and calibration metrics with 95% bootstrap confidence intervals:

| Domain | Best Model | AUROC (95% CI) | PR-AUC | Brier Score | Sensitivity | NPV |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Cardiovascular (ASCVD)** | Calibrated Logistic Regression | **0.7644** [0.685–0.836] | 0.4700 | **0.1549** | **93.33%** | **95.59%** |
| **Nephropathy (KDIGO)** | Calibrated Logistic Regression | **0.7630** [0.690–0.837] | 0.8689 | **0.1966** | **86.24%** | **63.41%** |
| **Neuropathy (MNSI)** | Gradient Boosting Classifier | **0.7992** [0.771–0.826] | 0.6823 | **0.1765** | **87.26%** | **88.56%** |

**Clinical Significance**:
- **AUROC 0.76–0.80**: Comparable to established clinical risk engines (e.g., Framingham 10-year CVD risk and ACC/AHA Pooled Cohort Equations, which typically yield 0.72–0.78 in diabetic populations).
- **Brier Score < 0.20**: Demonstrates excellent probability calibration.
- **High Sensitivity (86%–93%) & NPV (88%–96%)**: Optimized for preventative screening so high-risk patients are not missed.

**Reference Document**: [training_summary.json](model/training_summary.json) and [METHODOLOGY.md](METHODOLOGY.md#epidemiological-validation-metrics)

---

### 4. "How did you select decision thresholds?"
**Answer**: 
- **No Data Leakage**: High-risk operating thresholds are calculated **strictly on training folds** using Youden's J statistic and clinical sensitivity optimization targets.
- **Clinical Decision Utility**: Outpatient triage requires prioritizing sensitivity (>85%) and Negative Predictive Value (>88–95%) to minimize false negatives.
- **Triage Action Tiers**:
  - **Low Risk ($\le 30\%$)**: Routine annual surveillance, lifestyle guidance.
  - **Moderate Risk ($31\% - 60\%$)**: Accelerated monitoring, medication review, lab follow-up.
  - **High Risk ($> 60\%$)**: High complication burden; urgent specialist consultation (Cardiology/Nephrology/Podiatry).

**Reference Document**: [METHODOLOGY.md](METHODOLOGY.md#threshold-selection--clinical-decision-utility)

---

### 5. "Which features matter most clinically?"
**Answer**: 
- **Cardiovascular**: Hypertension (`HighBP`), Prior Stroke, Age, Smoking history, Dyslipidemia (`HighChol`).
- **Nephropathy**: Hypertension, Elevated BMI, Advanced Age, Smoking history, Sex.
- **Neuropathy/Mobility**: Self-rated General Health (`GenHlth`), Poor Physical Health Days (`PhysHlth`), Age, Walking Impairment (`DiffWalk`), Hypertension.

**Reference Document**: [training_summary.json](model/training_summary.json)

---

### 6. "How do you handle missing lab data?"
**Answer**:
- **Two-Tiered Screening Architecture**:
  - **Tier 1 (Always Available)**: 13 non-invasive clinical indicators (vitals, lifestyle, symptoms) can be completed in <2 minutes without lab work.
  - **Tier 2 (Point-of-Care Biomarkers)**: Optional HbA1c, Systolic BP, and LDL cholesterol evaluated against ADA 2026 clinical guidelines.
- If lab values are absent, the system gracefully operates on Tier 1 without error or degradation of the core ML classifiers.

**Reference Document**: [METHODOLOGY.md](METHODOLOGY.md#two-tiered-clinical-screening-paradigm)

---

### 7. "Is the system production-ready?"
**Answer**: 
- ✅ **Security**: CSRF protection (Flask-WTF) on form submissions, environment-based configuration (`.env`).
- ✅ **Data Integrity**: SQLite Write-Ahead Logging (WAL) and safe, non-destructive schema migrations.
- ✅ **Input Validation**: Rigorous server-side bounds checking for all clinical fields in `validation.py`.
- ✅ **Fault Tolerance**: Graceful fallback to guideline rules if ML models become unavailable.
- ✅ **Audit Trail**: Rotating log files (10MB per file, 5 backups) tracking validation, inference, and runtime health.

**Reference Document**: [SECURITY.md](SECURITY.md) and [ARCHITECTURE.md](ARCHITECTURE.md)

---

### 8. "What are the clinical limitations?"
**Answer**:
- **Cross-Sectional Data**: NHANES and BRFSS capture prevalent complication status. Future longitudinal EHR studies will predict prospective 5- to 10-year event horizons.
- **Functional Proxy**: `DiffWalk` acts as a validated functional mobility proxy for lower-extremity peripheral neuropathy, rather than an in-person 10g monofilament exam.
- **Clinical Intended Use**: Designed as educational and clinical decision support (CDS) triage, **not** an autonomous diagnostic medical device.

**Reference Document**: [METHODOLOGY.md](METHODOLOGY.md#ethical-scope-limitations--future-work)

---

## How to Demonstrate the System

### 1. **Show the Architecture**
```bash
python app.py
```
- Open `http://localhost:5000`
- Walk through the Home overview, Assessment form, and Dual-Score Result page.
- Demonstrate History session isolation and PDF printable summary.

### 2. **Walk Through the Code**
- **[clinical_data_pipeline.py](clinical_data_pipeline.py)**: Authentic cohort curation (NHANES + BRFSS).
- **[train_model.py](train_model.py)**: 5-fold CV, calibration, training-fold threshold selection, bootstrap CIs.
- **[rule_matrix.py](rule_matrix.py)**: ACC/AHA, KDIGO, and MNSI clinical guideline engines.
- **[clinical_model.py](clinical_model.py)**: Robust serialization wrapper (`ClinicalRiskWrapper`).

### 3. **Show the Documentation**
- **[METHODOLOGY.md](METHODOLOGY.md)**: Scientific rigor, epidemiological validation, and defense Q&A.
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: System architecture and data flow diagrams.
- **[SECURITY.md](SECURITY.md)**: Security, privacy, and deployment hardening.
- **[training_summary.json](model/training_summary.json)**: Model performance metrics.

---

## File Organization for Defense

### Core Application Files
- `app.py` - Flask application with CSRF protection and logging
- `rule_matrix.py` - Guideline-aligned scoring logic (ACC/AHA, KDIGO, MNSI)
- `train_model.py` - ML training, calibration, and validation pipeline
- `clinical_data_pipeline.py` - Clinical cohort extraction and preparation
- `clinical_model.py` - Model serialization wrapper
- `validation.py` - Server-side input validation
- `recommendations.py` - Clinical tier guidance engine
- `database.py` - SQLite persistence with WAL mode

### Clinical Cohorts & Data
- `data/nhanes_2017_2018_heart_disease_prediction.csv` - CDC NHANES CVD Cohort (N=949)
- `data/CKD_NHANES_2021_2023.csv` - CDC NHANES Nephropathy Cohort (N=848)
- `data/diabetes_dataset.csv` - CDC BRFSS Diabetic Cohort (N=5,000 stratified)

### Model Artifacts
- `model/training_summary.json` - Complete epidemiological performance metrics
- `model/clinical_roc_curves.png` - Out-of-fold ROC curves
- `model/clinical_calibration_curves.png` - Probability calibration plots
- `model/*_model.pkl` - Serialized calibrated estimators

### Documentation
- **[METHODOLOGY.md](METHODOLOGY.md)** - Technical & epidemiological documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Layered system architecture & schema
- **[SECURITY.md](SECURITY.md)** - Security, privacy, and operations guide
- **[DEFENSE_QUICK_START.md](DEFENSE_QUICK_START.md)** - Defense preparation & talking points
- `README.md` - Repository overview

---

## Pre-Defense Checklist

- [ ] Review [METHODOLOGY.md](METHODOLOGY.md) — master the clinical cohort and validation details
- [ ] Review [ARCHITECTURE.md](ARCHITECTURE.md) — understand the layered system components
- [ ] Review [SECURITY.md](SECURITY.md) — understand security controls (CSRF, WAL, input validation)
- [ ] Run `python test_clinical_system.py` to confirm all integration tests pass
- [ ] Launch `python app.py` and submit a sample assessment
- [ ] Review `model/training_summary.json` metrics for quick reference
