# Documentation Index

| Document | Use it for |
|---|---|
| [README.md](README.md) | Setup, scope, routes, active metrics, and file map |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Request flow, components, storage, and deployment |
| [METHODOLOGY.md](METHODOLOGY.md) | Cohorts, targets, training, metrics, thresholds, and limitations |
| [SECURITY.md](SECURITY.md) | Environment variables, controls, privacy, and deployment |
| [DEPLOYMENT_HARDENING.md](DEPLOYMENT_HARDENING.md) | Clean-machine Windows pilot matrix, recovery, and support diagnostics |
| [DEFENSE_QUICK_START.md](DEFENSE_QUICK_START.md) | Demonstration and current talking points |
| [FINAL_COMPLETION_REPORT.md](FINAL_COMPLETION_REPORT.md) | Current repository status and caveats |
| [FIXES_VERIFICATION.md](FIXES_VERIFICATION.md) | Verification scope and evidence |
| [HIGH_PRIORITY_FIXES.md](HIGH_PRIORITY_FIXES.md) | Deployment actions requiring attention |

## Authoritative Artifacts

- `model/training_summary.json`: active metrics, thresholds, subgroup analysis, and metadata.
- `test_clinical_system.py`: automated application checks.
- `app.py`, `database.py`, `train_model.py`, and `clinical_model.py`: runtime and model behavior.

## Quick Commands

- App: `python app.py`
- Tests: `python test_clinical_system.py`
- Waitress: `python wsgi.py`
- Docker: `docker compose up --build -d`
- Readiness: `GET /health`

Always check the active JSON and Python implementation before copying metrics or route claims into new documentation.
