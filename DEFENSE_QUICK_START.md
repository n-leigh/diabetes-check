# Defense Quick Start

## One-Minute Description

DiaBeates is a Flask decision-support prototype for diabetes-complication screening. It presents four calibrated model estimates beside transparent rule-matrix scores and stores results in session-isolated SQLite history. It is not a diagnostic device.

## Demonstration

```powershell
python test_clinical_system.py
python app.py
```

Open `http://127.0.0.1:5000`, complete an assessment, review results, open history, print or save as PDF, and show `/health`. Use `python wsgi.py` for the Waitress path.

## Talking Points

1. **Dual-Engine Architecture**: The clinical rule matrix generates transparent guideline scores and drives patient guidance recommendations. Calibrated ML estimators provide complementary empirical event probabilities displayed side-by-side without automating medical directives.
2. **Clinical Endpoints**: Targets are physician-diagnosed cardiovascular disease, laboratory-confirmed CKD (KDIGO), `DiffWalk` mobility impairment (functional proxy), and a clinical retinopathy screening endpoint.
3. **Training & Validation**: Training uses a stratified 80/20 split, candidate estimators with 5-fold cross-validation calibration (`CalibratedClassifierCV`), holdout test evaluation, and 1,000 bootstrap resamples for 95% confidence intervals.
4. **Validated Status**: All four complication models are validated. Retinopathy discrimination (AUROC 0.7491) was achieved through pooled CDC NHANES 2005–2008 cycles (N=1,323) to support screening and timely ophthalmology examination referral.
5. **Threshold Methodology**: Domain-specific cutoffs are derived from 5-fold cross-validation out-of-fold training predictions (not a universal 33/66 split or Youden's J). A screening threshold enforces a high sensitivity floor (>=85%) to minimize missed complications, while a referral threshold enforces a precision floor (>=60%) to prioritize patients requiring specialized clinical follow-up.
6. **Privacy & Security Controls**: Includes strict CSP (`'self'` only, zero external CDNs/fonts), CSRF protection, rate limiting, server-side bounds validation, anonymous session-isolated SQLCipher AES-256 encrypted WAL storage, DPAPI key protection, and startup retention pruning.

## Current Metrics

| Domain | AUROC | Brier | Status |
|---|---:|---:|---|
| Cardiovascular | 0.7638 | 0.1552 | Validated |
| CKD | 0.7624 | 0.1969 | Validated |
| Mobility | 0.7996 | 0.1758 | Validated |
| Retinopathy | 0.7491 | 0.2021 | Validated |

Do not present historical accuracy values as current evidence.
