# Verification Record

This file records checks meaningful for the current repository and replaces older fix-count and accuracy claims.

## Automated Check

Run `python test_clinical_system.py`. The suite covers rule calculations, database behavior, route responses, CSRF behavior, accessibility-related markup, security headers, and retention pruning.

## Current Implementation Checks

- `validation.py` rejects missing or out-of-range inputs and invalid optional labs.
- `app.py` logs model-loading failures and reports availability through `/health`.
- `database.py` uses foreign keys, WAL mode, schema version 4, session filtering, archive state, and dependent-row deletion.
- `train_model.py` evaluates calibrated logistic regression, random forest, and gradient boosting.
- `clinical_model.py` applies per-domain screening and referral thresholds.
- `Dockerfile` runs as `appuser` and probes `/health`.
- `wsgi.py` serves through Waitress with eight threads.

Passing tests does not establish clinical validity, external generalization, privacy compliance, or production readiness.
