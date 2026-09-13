# Current System Status

This is a current-state snapshot, not a historical completion claim.

## Verified State

- Flask assessment, result, history, print, feedback, and health routes.
- Four serialized models and matching entries in `model/training_summary.json`.
- Rule matrix version `2.0-clinical`.
- SQLite schema version 4 with WAL mode and additive initialization.
- CSRF, rate limiting, server-side validation, Waitress, and non-root Docker execution.
- Startup pruning controlled by `RETENTION_DAYS`.

## Current AUROC

| Domain | Model | AUROC | Status |
|---|---|---:|---|
| Cardiovascular | Calibrated Logistic Regression | 0.7638 | Validated |
| Nephropathy / CKD | Calibrated Logistic Regression | 0.7624 | Validated |
| Neuropathy / mobility | Calibrated Gradient Boosting | 0.7996 | Validated |
| Retinopathy | Calibrated Logistic Regression | 0.6418 | Experimental |

See [METHODOLOGY.md](METHODOLOGY.md) and `model/training_summary.json` for complete metrics.

## Known Caveats

- Missing or unreadable models make `/health` return HTTP 503 and are logged.
- Production should set `SECRET_KEY` explicitly; the fallback writes `.secret_key`.
- Compose does not configure HTTPS, a production secret, or secure cookies.
- The effective frame header is `SAMEORIGIN` because the later response hook overwrites `DENY`.
- Retinopathy remains experimental.

## Verification

```powershell
python test_clinical_system.py
```
