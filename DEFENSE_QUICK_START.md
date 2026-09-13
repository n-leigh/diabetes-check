# Defense Quick Start

## One-Minute Description

DiaBeates is a Flask decision-support prototype for diabetes-complication screening. It presents four calibrated model estimates beside transparent rule-matrix scores and stores results in session-isolated SQLite history. It is not a diagnostic device.

## Demonstration

```powershell
python test_clinical_system.py
python app.py
```

Open `http://127.0.0.1:5000`, complete an assessment, review results, open history, print a result, submit feedback, and show `/health`. Use `python wsgi.py` for the Waitress path.

## Talking Points

1. The rule matrix is inspectable; ML estimators learn empirical endpoints. They are displayed separately.
2. Targets are cardiovascular disease, CKD, `DiffWalk` mobility impairment, and a retinopathy endpoint. Mobility is not confirmed neuropathy.
3. Training uses a stratified 80/20 split, calibrated candidate models, untouched test evaluation, and bootstrap intervals.
4. Retinopathy AUROC is 0.6418 and status is experimental; it should support eye-exam referral, not precise diagnosis.
5. Thresholds are domain-specific and selected from training-fold out-of-fold predictions. There is no active universal 33/66 rule.
6. Controls include CSRF, rate limiting, server-side validation, session filtering, WAL storage, security headers, sanitized errors, and retention pruning.

## Current Metrics

| Domain | AUROC | Brier | Status |
|---|---:|---:|---|
| Cardiovascular | 0.7638 | 0.1552 | Validated |
| CKD | 0.7624 | 0.1969 | Validated |
| Mobility | 0.7996 | 0.1758 | Validated |
| Retinopathy | 0.6418 | 0.2341 | Experimental |

Do not present historical accuracy values as current evidence.
