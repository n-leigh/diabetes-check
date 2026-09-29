# Defense Quick Start

## One-Minute Description

DiaBeates is a Flask decision-support prototype for diabetes-complication screening. It presents four calibrated model estimates beside transparent rule-matrix scores and stores results in session-isolated SQLite history. It is not a diagnostic device.

## Demonstration

```powershell
python test_clinical_system.py
python app.py
```

Open `http://127.0.0.1:5000`, complete an assessment, review results, open history, print a result, test offline report sharing, and show `/health`. Use `python wsgi.py` for the Waitress path.

## Talking Points

1. The rule matrix is inspectable; ML estimators learn empirical endpoints. They are displayed separately.
2. Targets are cardiovascular disease, CKD, `DiffWalk` mobility impairment, and a retinopathy endpoint. Mobility is a functional deficit proxy, not confirmed neuropathy.
3. Training uses a stratified 80/20 split, calibrated candidate models, untouched test evaluation, and bootstrap intervals.
4. All four complication models are validated. Retinopathy discrimination was strengthened to AUROC 0.7491 by pooling CDC NHANES 2005–2008 cycles (N=1,323) with laboratory HbA1c; it supports screening and ophthalmology examination referral.
5. Thresholds are domain-specific and selected from training-fold out-of-fold predictions. There is no active universal 33/66 rule.
6. Controls include CSRF, rate limiting, server-side validation, session filtering, SQLCipher encrypted WAL storage, strict CSP headers, sanitized errors, and retention pruning.

## Current Metrics

| Domain | AUROC | Brier | Status |
|---|---:|---:|---|
| Cardiovascular | 0.7638 | 0.1552 | Validated |
| CKD | 0.7624 | 0.1969 | Validated |
| Mobility | 0.7996 | 0.1758 | Validated |
| Retinopathy | 0.7491 | 0.2021 | Validated |

Do not present historical accuracy values as current evidence.
