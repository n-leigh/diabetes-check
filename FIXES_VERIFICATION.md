# Verification Record

This file records checks meaningful for the current repository and replaces older fix-count and accuracy claims.

## Automated Checks

Run the automated verification suites:
- `python test_clinical_system.py`: covers rule matrix v2.0 calculations, model loading, route responses, CSRF rejection/acceptance, accessibility attributes, security headers, backup/restore, and retention pruning.
- `python test_privacy_hardening.py`: covers strict CSP, zero external CDN/font connections, in-memory execution, and WebCrypto URL-hash fragment sharing.
- `python test_storage_security.py`: covers SQLCipher encryption, user-scoped DPAPI key protection, and tampering rejection.

## Current Implementation Checks

- `validation.py` rejects missing or out-of-range inputs and invalid optional labs.
- `app.py` logs model-loading failures, executes in-memory assessments anonymously by default, and reports availability through `/health`.
- `database.py` enforces SQLCipher AES-256 encryption, foreign keys, WAL mode, schema version 4, session filtering, archive state, and dependent-row deletion.
- `train_model.py` evaluates calibrated logistic regression, random forest, and gradient boosting across all 4 complication domains, including pooled CDC NHANES 2005–2008 data with laboratory HbA1c.
- `clinical_model.py` applies per-domain screening and referral thresholds.
- `Dockerfile` runs as `appuser` and probes `/health`.
- `wsgi.py` serves through Waitress on `127.0.0.1` with eight threads.

Passing tests does not establish clinical validity, external generalization, privacy compliance, or production readiness.
