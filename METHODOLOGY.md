# Methodology

## Study Objective 5

1.3.2.5 To evaluate the performance of the machine-learning models using Weka
and report their accuracy and other relevant evaluation results.

### Aligned Statement of the Problem

5. How accurate are the machine-learning models when evaluated using Weka?

## Intended Use

DiaBeates provides screening-oriented estimates and educational guidance. It does not diagnose disease or predict validated 5- or 10-year event risk. All four domain models have undergone cross-validation and holdout evaluation.

## Cohorts and Targets

| Domain | Active training input | Size | Target |
|---|---|---:|---|
| Cardiovascular | `data/processed_cardiovascular_cohort.csv` | 949 | Physician-diagnosed coronary heart disease, angina, or myocardial infarction |
| Nephropathy / CKD | `data/processed_nephropathy_cohort.csv` | 848 | CKD based on eGFR < 60 or uACR >= 30 |
| Neuropathy / mobility | `data/diabetes_dataset.csv` | 5,000 sampled rows | `DiffWalk`, a lower-extremity mobility deficit |
| Retinopathy | `data/processed_retinopathy_cohort.csv` | 1,323 | Retinal examination and physician-diagnosed retinopathy endpoint with lab HbA1c |

Source descriptions identify CDC NHANES 2017-2018, CDC NHANES 2021-2023, BRFSS, and CDC NHANES 2005-2008 (pooled 2005–2006 and 2007–2008 cycles) respectively. Training uses the processed files listed above, except for the BRFSS dataset.

## Features

The web form collects 15 required clinical features (`HighBP`, `HighChol`, `Smoker`, `HeartDiseaseorAttack`, `Stroke`, `BMI`, `Age`, `DiffWalk`, `PhysHlth`, `GenHlth`, `MentHlth`, `NoDocbcCost`, `Sex`, `DiabetesDuration`, `BlurryVision`) plus three optional point-of-care laboratory biomarkers (`LabHbA1c`, `LabSystolicBP`, `LabLDL`). All submitted inputs are validated on the server; missing or out-of-bounds required inputs are rejected (no runtime imputation). Offline median imputation was used strictly during training cohort preparation.

Model subsets are: cardiovascular (`HighBP`, `HighChol`, `Smoker`, `Stroke`, `Age`, `Sex`); CKD (`HighBP`, `Smoker`, `BMI`, `Age`, `Sex`); mobility (`BMI`, `Age`, `PhysHlth`, `GenHlth`, `Smoker`, `HighBP`); retinopathy (`HighBP`, `HighChol`, `Smoker`, `BMI`, `Age`, `Sex`, `DiabetesDuration`, `BlurryVision`). Laboratory HbA1c is evaluated alongside systolic blood pressure and LDL by the clinical rule matrix.

## Training and Evaluation

`train_model.py` uses a stratified 80/20 split with `random_state=42`. Candidates are logistic regression, random forest, and gradient boosting. Logistic regression uses `StandardScaler`; candidate probabilities use sigmoid `CalibratedClassifierCV` with five folds on training data. The selected estimator is evaluated on the untouched test split.

Reported measures are AUROC, PR-AUC, Brier score, ECE, sensitivity, specificity, PPV, and NPV. AUROC and metric confidence intervals use 1,000 bootstrap resamples. Age and sex subgroup summaries flag groups with fewer than 30 observations or calibration error above 0.10.

## Active Results

| Domain | Model | AUROC (95% CI) | PR-AUC | Brier | ECE | Status |
|---|---|---:|---:|---:|---:|---|
| Cardiovascular | Calibrated Logistic Regression | 0.7638 (0.6840-0.8356) | 0.4696 | 0.1552 | 0.0485 | Validated |
| CKD | Calibrated Logistic Regression | 0.7624 (0.6896-0.8371) | 0.8684 | 0.1969 | 0.0879 | Validated |
| Mobility | Calibrated Gradient Boosting | 0.7996 (0.7718-0.8262) | 0.6856 | 0.1758 | 0.0425 | Validated |
| Retinopathy | Calibrated Logistic Regression | 0.7491 (0.6898-0.8047) | 0.6863 | 0.2021 | 0.0488 | Validated |

Complete metrics, thresholds, subgroup results, and reliability tables are in `model/training_summary.json`.

## Rule Matrix, Thresholds, and Guidance

`rule_matrix.py` is version `2.0-clinical`; it maps each independent rule score to `Low` (<=30%), `Moderate` (31-60%), or `High` (>60%). Optional HbA1c, systolic BP, and LDL values receive a separate lab assessment. Patient guidance recommendations are generated deterministically from the clinical rule matrix and laboratory values, while the ML estimators provide complementary empirical risk probability estimates.

ML thresholds are domain-specific and derived from 5-fold cross-validation out-of-fold training predictions (not a universal 33/66 split or Youden's J). A screening threshold enforces a high sensitivity floor (>=85%) to minimize missed complications, while a referral threshold enforces a precision floor (>=60% with specificity >=40%) to prioritize patients requiring specialized clinical follow-up:

| Domain | Screening | Referral |
|---|---:|---:|
| Cardiovascular | 0.1734 | 0.1880 |
| CKD | 0.5522 | 0.6522 |
| Mobility | 0.2429 | 0.2865 |
| Retinopathy | 0.2964 | 0.4001 |

## Limitations

The cohorts are cross-sectional and survey-based; `DiffWalk` is a mobility proxy rather than a neurological examination; the form lacks variables used by established calculators; sampling, coding, missingness, and cohort sizes limit transportability; subgroup evidence is uneven; and retinopathy should guide examination referral rather than probability-based diagnosis.

## Results Chapter Draft: Results per Specific Objective

The following structure may be used for the Results chapter. Each section
states the objective, presents the evidence, and explains what the result
means. Screenshots should support the written results, not replace tables or
interpretation.

### Objective 1: Structured Assessment

**Objective.** To design and organize a structured assessment using
self-reported health indicators and optional clinical laboratory values.

**Result.** The system implemented a three-step assessment. It collects 15
required health indicators and accepts three optional laboratory values:
HbA1c, systolic blood pressure, and LDL cholesterol. These inputs support
separate screening estimates for cardiovascular disease, kidney disease,
nerve and mobility problems, and diabetic retinopathy.

**Suggested screenshot:** `Figure 1. Structured health assessment form`

**Table 1. Assessment variables and their purpose**

| Variable group | Variables included | Use in the system |
|---|---|---|
| Personal information | Age, sex, BMI, diabetes duration | Model features and rule-based scoring |
| Health conditions | High blood pressure, high cholesterol, smoking, heart disease or heart attack, stroke | Model features and rule-based scoring |
| Mobility and vision | Difficulty walking, blurry vision | Model features and rule-based scoring |
| Health and access | Physical health days, general health, mental health days, skipped doctor visit because of cost | Rule-based scoring and explanations |
| Optional laboratory values | HbA1c, systolic blood pressure, LDL cholesterol | Additional laboratory assessment |

**Table 1A. Number of assessment inputs**

| Input type | Number |
|---|---:|
| Required health indicators | 15 |
| Optional laboratory values | 3 |
| Total available inputs | 18 |

**Interpretation.** The structured form organized the required health
information in one assessment while allowing users to provide laboratory
values only when available.

### Objective 2: Rule-Based Scoring Algorithm

**Objective.** To develop a weighted rule-based scoring algorithm through a
rule matrix that produces Low, Moderate, and High classifications.

**Result.** The rule matrix converted selected answers into a score,
percentage, and risk classification for each complication domain. The
classification thresholds were Low (up to 30%), Moderate (31% to 60%), and
High (above 60%). The system also displayed the factors that affected each
classification.

**Suggested screenshot:** `Figure 2. Rule-based risk classifications on the results page`

**Table 2. Rule-based scoring output by complication domain**

| Complication domain | Output shown to the user |
|---|---|
| Cardiovascular disease | Score, percentage, and Low/Moderate/High classification |
| Kidney disease | Score, percentage, and Low/Moderate/High classification |
| Nerve and mobility problems | Score, percentage, and Low/Moderate/High classification |
| Diabetic retinopathy | Score, percentage, and Low/Moderate/High classification |

**Table 2A. Rule-based classification thresholds**

| Classification | Score percentage | Meaning |
|---|---:|---|
| Low | 0% to 30% | Lower screening risk |
| Moderate | 31% to 60% | Screening result should be discussed with a healthcare professional |
| High | Above 60% | Prompt healthcare follow-up is recommended |

**Interpretation.** The rule matrix made the screening result transparent.
Users could see both their classification and the health factors associated
with it. These classifications are screening guidance and not diagnoses.

### Objective 3: Calibrated Machine-Learning Models

**Objective.** To develop and evaluate calibrated Logistic Regression, Random
Forest, and Gradient Boosting models using empirical complication outcomes.

**Result.** Candidate models were compared using stratified training and
cross-validation. The selected models were then evaluated on untouched test
data. The verified discrimination results are shown below.

**Suggested screenshot:** `Figure 3. Machine-learning predictions displayed with rule-based results`

**Table 3. Selected model performance on the held-out test data**

| Domain | Selected model | Test size | AUROC (95% CI) | PR-AUC | Brier score | ECE |
|---|---|---:|---:|---:|---:|---:|
| Cardiovascular | Calibrated Logistic Regression | 190 | 0.7638 (0.6840-0.8356) | 0.4696 | 0.1552 | 0.0485 |
| Kidney disease | Calibrated Logistic Regression | 170 | 0.7624 (0.6896-0.8371) | 0.8684 | 0.1969 | 0.0879 |
| Nerve and mobility | Calibrated Gradient Boosting | 1,000 | 0.7996 (0.7718-0.8262) | 0.6856 | 0.1758 | 0.0425 |
| Diabetic retinopathy | Calibrated Logistic Regression | 265 | 0.7491 (0.6898-0.8047) | 0.6863 | 0.2021 | 0.0488 |

**Table 4. Selected model classification results at the screening threshold**

| Domain | Threshold | Accuracy | Sensitivity | Specificity | F1-score |
|---|---:|---:|---:|---:|---:|
| Cardiovascular | 0.1734 | 56.32% | 93.33% | 44.83% | 0.5030 |
| Kidney disease | 0.5522 | 70.59% | 86.24% | 42.62% | 0.7899 |
| Nerve and mobility | 0.2429 | 68.60% | 87.53% | 57.53% | 0.6729 |
| Diabetic retinopathy | 0.3286 | 58.75% | 86.76% | 38.04% | 0.6413 |

**Interpretation.** The models provided calibrated probability estimates
alongside the rule-based classifications. The AUROC values ranged from
0.7491 to 0.7996. The screening thresholds prioritized sensitivity, which
helps reduce missed positive cases but may produce more false positives.

### Objective 4: User Interface

**Objective.** To design and implement an interface that presents risk
scores, model predictions, explanations, recommendations, and optional
laboratory assessments clearly.

**Result.** The completed interface guides the user through the assessment,
displays the four domain results, shows factors affecting each result, and
provides recommendations and doctor discussion points. Optional laboratory
results are shown when the user enters them.

**Suggested screenshots:**

- `Figure 4. DiaBeates home page`
- `Figure 5. Three-step assessment interface`
- `Figure 6. Results page with four complication domains`
- `Figure 7. Optional laboratory assessment panel`
- `Figure 8. Recommendations and questions for the doctor`

**Table 5. Interface functions and supporting evidence**

| Interface function | Screenshot or evidence |
|---|---|
| Assessment intake | Figure 5: Three-step assessment interface |
| Risk classification | Figure 6: Results page with four complication domains |
| Model prediction | Figure 6: Model estimate and risk label |
| Risk explanation | Figure 6: Factors affecting the result |
| Laboratory assessment | Figure 7: Optional laboratory assessment panel |
| Guidance | Figure 8: Recommendations and questions for the doctor |

**Interpretation.** The interface brought the rule-based score, model
prediction, explanation, and guidance together in one patient-facing flow.
The screenshots demonstrate how the implemented functions appear to users.

### Objective 5: Weka Evaluation

**Objective.** To evaluate the performance of the machine-learning models
using Weka and report their accuracy and other relevant evaluation results.

**Method.** Import the same prepared dataset and target variable used for each
domain. Record the Weka classifier, preprocessing steps, test method, random
seed, and number of instances. Use the same evaluation method for each model
so the results can be compared fairly.

**Suggested screenshot:** `Figure 9. Weka evaluation output`

**Table 6. Weka model evaluation results**

| Domain/model | Evaluation method | Accuracy | Precision | Recall | F1-score | ROC area |
|---|---|---:|---:|---:|---:|---:|
| Cardiovascular | [enter method] | [enter %] | [enter] | [enter] | [enter] | [enter] |
| Kidney disease | [enter method] | [enter %] | [enter] | [enter] | [enter] | [enter] |
| Nerve and mobility | [enter method] | [enter %] | [enter] | [enter] | [enter] | [enter] |
| Diabetic retinopathy | [enter method] | [enter %] | [enter] | [enter] | [enter] | [enter] |

**Table 7. Weka confusion matrices**

| Domain/model | True negatives | False positives | False negatives | True positives |
|---|---:|---:|---:|---:|
| Cardiovascular | [enter] | [enter] | [enter] | [enter] |
| Kidney disease | [enter] | [enter] | [enter] | [enter] |
| Nerve and mobility | [enter] | [enter] | [enter] | [enter] |
| Diabetic retinopathy | [enter] | [enter] | [enter] | [enter] |

**Interpretation template.** The Weka evaluation showed an accuracy of
**[enter %]** for the **[model/domain]** model. Its ROC area was **[enter]**,
indicating **[limited/moderate/good]** ability to distinguish between the two
outcome classes. The precision, recall, and F1-score were **[enter]**,
**[enter]**, and **[enter]**, respectively. These results should be compared
with the other models using the same evaluation method.

If Weka trains new models rather than loading the models used by the website,
state that Weka provided an independent comparison. Do not describe the Weka
values as identical to the deployed Flask model results. Accuracy should also
be interpreted together with precision, recall, F1-score, ROC area, and the
confusion matrix, especially when the outcome classes are imbalanced.
