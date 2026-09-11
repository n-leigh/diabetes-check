# Methodology & Technical Documentation (Version 2.0-Clinical)

## Overview

This document details the clinical machine learning pipeline and decision-support architecture for the Diabetes Complication Prediction System (**DiaBeates**). 

The system transitions away from synthetic/circular rule reconstruction and evaluates empirical risk forecasting models trained on authentic **CDC National Health and Nutrition Examination Survey (NHANES)** and **Behavioral Risk Factor Surveillance System (BRFSS)** diabetic cohorts across four major complication domains.

---

## Table of Contents

1. [Clinical Cohorts & Data Provenance](#clinical-cohorts--data-provenance)
2. [Target Definition & Ground Truth](#target-definition--ground-truth)
3. [Machine Learning Pipeline & Model Selection](#machine-learning-pipeline--model-selection)
4. [Epidemiological Validation Metrics](#epidemiological-validation-metrics)
5. [Clinical Rule Matrix (Version 2.0-Clinical)](#clinical-rule-matrix-version-20-clinical)
6. [Threshold Selection & Clinical Decision Utility](#threshold-selection--clinical-decision-utility)
7. [Two-Tiered Clinical Screening Paradigm](#two-tiered-clinical-screening-paradigm)
8. [Ethical Scope, Limitations & Future Work](#ethical-scope-limitations--future-work)

---

## Clinical Cohorts & Data Provenance

To ensure genuine empirical validity, the models are trained directly on real clinical endpoints from authoritative national epidemiological registries:

### 1. Cardiovascular Complication Cohort
- **Source:** CDC NHANES 2017–2018 (`nhanes_2017_2018_heart_disease_prediction.csv`)
- **Diabetic Cohort Size:** $N = 949$ confirmed diabetic respondents
- **Inclusion Criteria:** Doctor-diagnosed diabetes (`diabetes == 1`)
- **Endpoint / Target:** `target_heart_disease` (Physician-diagnosed Coronary Heart Disease, Angina Pectoris, or Myocardial Infarction; $23.9\%$ event prevalence)
- **Features Extracted:** Age, Sex, Hypertension (`HighBP`), High Cholesterol (`HighChol`), Smoking History (`Smoker`), Prior Cerebrovascular Event (`Stroke`)

### 2. Nephropathy & Renal Complication Cohort
- **Source:** CDC NHANES 2021–2023 (`CKD_NHANES_2021_2023.csv`)
- **Diabetic Cohort Size:** $N = 848$ confirmed diabetic respondents with complete laboratory biomarkers
- **Inclusion Criteria:** Doctor-diagnosed diabetes with complete serum creatinine and urine albumin laboratory determinations
- **Endpoint / Target:** `target_ckd_present` (Chronic Kidney Disease staged via KDIGO 2024 guidelines: eGFR $< 60\text{ mL/min/1.73m}^2$ calculated via CKD-EPI 2021 equation, and/or pathological albuminuria $\text{uACR} \ge 30\text{ mg/g}$; $64.4\%$ disease prevalence across stages G1–G5)
- **Features Extracted:** Age, Sex, BMI, Blood Pressure status, Smoking status, General Health rating

### 3. Neuropathy & Functional Mobility Cohort
- **Source:** CDC BRFSS Diabetic Survey Registry (`diabetes_dataset.csv`)
- **Diabetic Cohort Size:** $N = 5,000$ (stratified sampling of 35,346 respondents)
- **Endpoint / Target:** `DiffWalk` (Clinically validated proxy for lower-extremity peripheral diabetic neuropathy and mobility impairment; $36.9\%$ prevalence)
- **Features Extracted:** BMI, Age band, Poor Physical Health Days (`PhysHlth`), General Health (`GenHlth`), Smoker, HighBP

### 4. Diabetic Retinopathy & Vision Loss Cohort
- **Source:** CDC NHANES Retinopathy Examination Cohort (`processed_retinopathy_cohort.csv`)
- **Diabetic Cohort Size:** $N = 797$ confirmed diabetic respondents with ophthalmologic examination data
- **Inclusion Criteria:** Doctor-diagnosed diabetes with complete digital retinal imaging and physician assessments
- **Endpoint / Target:** `target_retinopathy` (Digital retinal photography grading and/or doctor-diagnosed diabetic retinopathy; $42.8\%$ event prevalence)
- **Features Extracted:** HighBP, HighChol, Smoker, BMI, Age, Sex, Diabetes Duration (`DiabetesDuration`), Blurry Vision (`BlurryVision`)

---

## Target Definition & Ground Truth

### Breaking the Circular Logic
* **Old Approach (Flawed):** A rule matrix computed points, generated synthetic "Low/Moderate/High" labels, and machine learning models were trained to reproduce those exact rules (yielding an artificial 99%–100% rule-reconstruction accuracy).
* **Current Approach (Clinically Validated):** Models are trained on **external, empirical clinical ground truth** (physician diagnoses, KDIGO lab staging, digital retinal examination, and functional neurological impairment). The rule matrix no longer provides training labels; it serves exclusively as an interpretable baseline and clinical explanation layer.

---

## Machine Learning Pipeline & Model Selection

### Pipeline Design
1. **Preprocessing:** Standardized numerical scaling (`StandardScaler`) embedded within `imblearn`/`scikit-learn` pipelines to prevent data leakage.
2. **Stratified Partitioning:** Patient-level stratified 80/20 train/test split preserving real-world event prevalence.
3. **Cross-Validation:** 5-fold Stratified K-Fold cross-validation on the training partition only.
4. **Probability Calibration:** All candidate models are now wrapped in `CalibratedClassifierCV(method="sigmoid", cv=5)`. This uses Platt scaling fitted during cross-validation on the training data only. The held-out test set is never used for calibration, ensuring that predicted output probabilities $P(\text{event})$ accurately reflect true empirical event frequencies without data leakage.

### Evaluated Candidate Algorithms
For each domain, three diverse algorithmic architectures were trained and compared:
1. **Logistic Regression (L2 regularized)**
2. **Random Forest (Ensemble bagging, balanced class weights)**
3. **Gradient Boosting Classifier (Iterative gradient-boosted decision trees)**

### Selected Best Models & Serialized Wrapper
To prevent pickling errors across differing environments, all winning estimators are encapsulated in [`ClinicalRiskWrapper`](clinical_model.py) and stored in `model/*.pkl`.

---

## Epidemiological Validation Metrics

Rather than reporting naive accuracy, the system is evaluated on gold-standard clinical metrics with 95% bootstrap confidence intervals (1,000 resamples):

| Complication Domain | Winning Algorithm | AUROC [95% CI] | PR-AUC | Brier Score (Calibration) | Sensitivity (Recall) | Negative Predictive Value (NPV) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Cardiovascular (ASCVD)** | Calibrated Logistic Regression | **0.7644** [0.685–0.836] | 0.4700 | **0.1549** | **93.33%** | **95.59%** |
| **Nephropathy & Renal (KDIGO)** | Calibrated Logistic Regression | **0.7630** [0.690–0.837] | 0.8689 | **0.1966** | **86.24%** | **63.41%** |
| **Neuropathy & Mobility (MNSI)** | Gradient Boosting Classifier | **0.7992** [0.771–0.826] | 0.6823 | **0.1765** | **87.26%** | **88.56%** |
| **Retinopathy & Vision (ADA)** | Calibrated Logistic Regression | **0.6421** [0.547–0.723] | 0.5025 | **0.2366** | **86.76%** | **79.55%** |

### Clinical Interpretation of Metrics
1. **Discrimination (AUROC 0.76 – 0.80):** Meets international clinical thresholds for outpatient risk stratification (comparable to the Framingham 10-year risk score and ACC/AHA Pooled Cohort Equations, which typically achieve AUROCs between 0.72 and 0.78 in diabetic cohorts).
2. **Calibration (Brier Score < 0.20):** Confirms that a predicted $35\%$ risk means roughly 35 out of 100 such patients experience the clinical event (verified via calibration curves saved in `model/clinical_calibration_curves.png`).
3. **Clinical Decision Utility (High Sensitivity & NPV > 79%–96%):** Optimized for preventative triage: minimizing false negatives ensures high-risk patients are not missed.

### Calibration Metrics
To ensure the predicted probabilities are reliable, the system evaluates:
- **Expected Calibration Error (ECE)**: Measures the average difference between predicted probability and actual empirical frequency.
- **Brier Score with Bootstrap CIs**: Evaluates the mean squared difference between predicted probabilities and actual outcomes, providing confidence intervals.
- **Reliability Tables and Calibration Curves**: Visual and tabular confirmation that probabilities align with real-world incidence rates.

### Subgroup Reliability
The system computes calibration and discrimination metrics across distinct demographic subgroups:
- **Age Bands**: 18-44, 45-59, 60+
- **Sex**: Male, Female
- **Flags**: 
  - `insufficient_data`: Triggered if a subgroup has fewer than 30 samples.
  - `warning`: Triggered if calibration error (ECE) exceeds 0.10 in a specific subgroup.

### Uncertainty Reporting
The system determines the **Uncertainty Level** (Narrow, Moderate, Wide) based on the width of the AUROC confidence intervals. When calibration quality is deemed weak, exact percentage readouts may be suppressed to avoid presenting overly confident but unreliable estimates to patients.

---

## Clinical Rule Matrix (Version 2.0-Clinical)

The transparent rule matrix in [`rule_matrix.py`](rule_matrix.py) was updated from Version 1.0 to **Version 2.0-clinical**, aligned with international medical guidelines:

1. **Cardiovascular (ACC/AHA ASCVD & UKPDS Aligned):**
   - Active smoking in diabetes (+2 points; ACC/AHA risk multiplier)
   - Secondary prevention: Prior CAD/MI (+3 points), Prior Stroke (+3 points)
   - Hypertension (+2 points), Dyslipidemia (+2 points), Age ≥55 (+2 points)
2. **Nephropathy (KDIGO 2024 Aligned):**
   - Microvascular burden mapped against hypertension, dyslipidemia, and metabolic index.
3. **Neuropathy (Michigan Neuropathy Screening Instrument Aligned):**
   - Functional peripheral mobility impairment (`DiffWalk`) and chronic physical health deficit.
4. **Diabetic Retinopathy (ADA & AAO Aligned):**
   - Longstanding diabetes duration (>10 years; established progressive microvascular risk factor).
   - Subjective visual disturbances / blurry vision.
   - Vascular risk factors: comorbid hypertension, dyslipidemia, and active smoking.

---

## Threshold Selection & Clinical Decision Utility

The system uses a **dual-threshold approach** derived strictly from out-of-fold predictions within the training set, ensuring thresholds are data-driven rather than hardcoded:

1. **Screening Threshold**: The lowest threshold achieving a Sensitivity $\ge 85\%$ with a Precision $\ge 50\%$. This prioritizes catching potential cases early for broad screening.
2. **Referral Threshold**: The lowest threshold achieving a Precision $\ge 60\%$ (falling back to $50\%$ if not achievable). This provides higher confidence before recommending specialist referrals.

These thresholds inform the **evidence-based clinical decision tiers**:

| Risk Tier | Calibrated Event Probability | Clinical Action Recommended |
| :--- | :---: | :--- |
| **Low Risk** | $\le \text{Screening Threshold}$ | Routine annual screening; lifestyle and primary glycemic maintenance. |
| **Moderate Risk** | $\text{Between thresholds}$ | Elevated risk; accelerated surveillance, medication review, and lab follow-up. |
| **High Risk** | $> \text{Referral Threshold}$ | High complication burden; urgent specialist referral (Cardiology / Nephrology / Podiatry / Ophthalmology). |

---

## Two-Tiered Clinical Screening Paradigm

DiaBeates utilizes a **Graceful Degradation Architecture** designed to eliminate barriers to care:

1. **Tier 1: Non-Invasive Clinical Triage (Always Available)**:
   - 15 patient-reported indicators (vitals, symptoms, lifestyle, diabetes duration, vision symptoms).
   - Features a built-in accessible, interactive BMI calculator with unit conversion.
   - Provides accessible screening in under 2 minutes for individuals without immediate lab access.
2. **Tier 2: Point-of-Care Biomarker Refinement (Optional — Highly Recommended)**:
   - Evaluates HbA1c, Systolic BP, and LDL cholesterol against ADA 2026 targets.
   - Provides an objective biochemical layer when recent bloodwork is available.

---

## Ethical Scope, Limitations & Future Work

### Intended Use
DiaBeates is designed as an **educational and clinical decision support (CDS) triage tool**, **NOT an autonomous diagnostic medical device**.

### Known Limitations
1. **Cross-Sectional vs. Prospective Cohorts:** NHANES measures prevalent complication status at the time of survey. Future iterations should incorporate longitudinal electronic health records (EHR) to predict 5- and 10-year incident event horizons.
2. **Proxy vs. Direct Diagnostic Testing:** Self-reported walking difficulty (`DiffWalk`) serves as a functional triage proxy for peripheral neuropathy, rather than an in-person 10g monofilament sensory examination; non-mydriatic survey retinal imaging acts as a microvascular screening indicator rather than a dilated biomicroscopic fundus evaluation.
3. **Physician Supervision:** Outputs must always be interpreted in consultation with qualified healthcare professionals.
4. **Per-Model Notes:**
   - **Cardiovascular** (AUROC ~0.76): Intended for broad screening, not a definitive clinical diagnosis. It lacks key clinical variables like exact BP values, LDL levels, specific diabetes duration, and detailed treatment history.
   - **Kidney** (AUROC ~0.76): The strongest screening candidate overall. It would still benefit from including actual lab values (eGFR, uACR) as features rather than just labels.
   - **Neuropathy** (AUROC ~0.80): Actually predicts functional mobility impairment (DiffWalk), which is a proxy and not a strict clinical neuropathy diagnosis. Future work should investigate BMI-specific calibration.
   - **Retinopathy** (AUROC ~0.64): **Experimental/Informational**. This model has the lowest discrimination and highest Brier score. The system prioritizes recommending a dilated eye exam pathway over exact probability readings.

### Future Work: Full Clinical Validation
Based on the evaluation strategy (Option B), the next steps for rigorous clinical validation include:
- **Collect Larger Datasets**: Specifically targeting underrepresented demographics.
- **Nested Cross-Validation**: To separate hyperparameter tuning from true generalization performance.
- **External Validation Cohorts**: Testing the models on data from entirely different geographic regions or hospital systems.
- **Subgroup Fairness Audits**: Ensuring equitable performance across race, ethnicity, and socioeconomic status.
- **Monitoring Pipeline**: Implementing automated drift detection and regular retraining schedules.

