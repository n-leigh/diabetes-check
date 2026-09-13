# Methodology

## Intended Use

DiaBeates provides screening-oriented estimates and educational guidance. It does not diagnose disease or predict validated 5- or 10-year event risk. The retinopathy model is explicitly experimental.

## Cohorts and Targets

| Domain | Active training input | Size | Target |
|---|---|---:|---|
| Cardiovascular | `data/processed_cardiovascular_cohort.csv` | 949 | Physician-diagnosed coronary heart disease, angina, or myocardial infarction |
| Nephropathy / CKD | `data/processed_nephropathy_cohort.csv` | 848 | CKD based on eGFR < 60 or uACR >= 30 |
| Neuropathy / mobility | `data/diabetes_dataset.csv` | 5,000 sampled rows | `DiffWalk`, a lower-extremity mobility deficit |
| Retinopathy | `data/processed_retinopathy_cohort.csv` | 797 | Retinal examination and physician-diagnosed retinopathy endpoint |

Source descriptions identify CDC NHANES 2017-2018, CDC NHANES 2021-2023, BRFSS, and CDC NHANES 2007-2008 respectively. Training uses the processed files listed above, except for the BRFSS dataset.

## Features

The shared form feature set is `HighBP`, `HighChol`, `Smoker`, `HeartDiseaseorAttack`, `Stroke`, `BMI`, `Age`, `DiffWalk`, `PhysHlth`, `GenHlth`, `MentHlth`, `NoDocbcCost`, `Sex`, `DiabetesDuration`, and `BlurryVision`.

Model subsets are: cardiovascular (`HighBP`, `HighChol`, `Smoker`, `Stroke`, `Age`, `Sex`); CKD (`HighBP`, `Smoker`, `BMI`, `Age`, `Sex`); mobility (`BMI`, `Age`, `PhysHlth`, `GenHlth`, `Smoker`, `HighBP`); retinopathy (`HighBP`, `HighChol`, `Smoker`, `BMI`, `Age`, `Sex`, `DiabetesDuration`, `BlurryVision`).

## Training and Evaluation

`train_model.py` uses a stratified 80/20 split with `random_state=42`. Candidates are logistic regression, random forest, and gradient boosting. Logistic regression uses `StandardScaler`; candidate probabilities use sigmoid `CalibratedClassifierCV` with five folds on training data. The selected estimator is evaluated on the untouched test split.

Reported measures are AUROC, PR-AUC, Brier score, ECE, sensitivity, specificity, PPV, and NPV. AUROC and metric confidence intervals use 1,000 bootstrap resamples. Age and sex subgroup summaries flag groups with fewer than 30 observations or calibration error above 0.10.

## Active Results

| Domain | Model | AUROC (95% CI) | PR-AUC | Brier | ECE | Status |
|---|---|---:|---:|---:|---:|---|
| Cardiovascular | Calibrated Logistic Regression | 0.7638 (0.6840-0.8356) | 0.4696 | 0.1552 | 0.0485 | Validated |
| CKD | Calibrated Logistic Regression | 0.7624 (0.6896-0.8371) | 0.8684 | 0.1969 | 0.0879 | Validated |
| Mobility | Calibrated Gradient Boosting | 0.7996 (0.7718-0.8262) | 0.6856 | 0.1758 | 0.0425 | Validated |
| Retinopathy | Calibrated Logistic Regression | 0.6418 (0.5463-0.7232) | 0.5019 | 0.2341 | 0.0624 | Experimental |

Complete metrics, thresholds, subgroup results, and reliability tables are in `model/training_summary.json`.

## Rule Matrix and Thresholds

`rule_matrix.py` is version `2.0-clinical`; it maps each independent rule score to `Low` (<=30%), `Moderate` (31-60%), or `High` (>60%). Optional HbA1c, systolic BP, and LDL values receive a separate lab assessment. Rules are explanatory and are not training labels.

ML thresholds are domain-specific and derived from training-fold out-of-fold predictions, not a universal 33/66 split:

| Domain | Screening | Referral |
|---|---:|---:|
| Cardiovascular | 0.1734 | 0.1880 |
| CKD | 0.5522 | 0.6522 |
| Mobility | 0.2429 | 0.2865 |
| Retinopathy | 0.3286 | 0.4001 |

## Limitations

The cohorts are cross-sectional and survey-based; `DiffWalk` is a mobility proxy rather than a neurological examination; the form lacks variables used by established calculators; sampling, coding, missingness, and cohort sizes limit transportability; subgroup evidence is uneven; and retinopathy should guide examination referral rather than probability-based diagnosis.
