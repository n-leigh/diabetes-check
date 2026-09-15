# DiaBeates

DiaBeates is a Flask web application for diabetes-complication screening and education. It combines an interpretable clinical rule matrix with four calibrated binary machine-learning estimators. It is a decision-support tool, not a diagnostic device; results must be reviewed with a qualified healthcare professional.

## Current Scope

The assessment accepts required numeric, binary, and categorical indicators plus optional HbA1c, systolic blood pressure, and LDL values. It produces separate results for cardiovascular disease, nephropathy/chronic kidney disease, neuropathy-related mobility impairment, and diabetic retinopathy/vision risk.

The rule engine reports a score, percentage, and `Low`/`Moderate`/`High` tier. ML models report a calibrated event probability and a lower, moderate, or higher estimated-risk label using domain-specific thresholds. These outputs are complementary, not interchangeable diagnoses.

## Active Model Results

Values are from `model/training_summary.json`. Evaluation uses an untouched 20% test split; confidence intervals use 1,000 bootstrap resamples.

| Domain | Selected model | AUROC (95% CI) | PR-AUC | Brier | ECE | Screen / referral | Status |
|---|---|---:|---:|---:|---:|---:|---|
| Cardiovascular | Calibrated Logistic Regression | 0.7638 (0.6840-0.8356) | 0.4696 | 0.1552 | 0.0485 | 0.1734 / 0.1880 | Validated |
| Nephropathy / CKD | Calibrated Logistic Regression | 0.7624 (0.6896-0.8371) | 0.8684 | 0.1969 | 0.0879 | 0.5522 / 0.6522 | Validated |
| Neuropathy / mobility | Calibrated Gradient Boosting | 0.7996 (0.7718-0.8262) | 0.6856 | 0.1758 | 0.0425 | 0.2429 / 0.2865 | Validated |
| Retinopathy | Calibrated Logistic Regression | 0.6418 (0.5463-0.7232) | 0.5019 | 0.2341 | 0.0624 | 0.3286 / 0.4001 | Experimental |

Retinopathy has weaker discrimination and remains experimental. No historical accuracy claim is used as the primary performance statement.

## Local Privacy Hardening & Operational Guarantees

- **100% Local Inference**: Assessments are scored entirely by the local Python/Flask application on the user's computer. The authentic scikit-learn models and evidence-based rule matrix execute within the local environment—never sent to cloud AI APIs, remote microservices, or external servers.
- **Zero Third-Party Telemetry / CDNs**: No remote fonts (Google Fonts removed in favor of native system font stacks), no remote CDNs (Tailwind CSS 3.4.17 compiled locally), and no remote analytics or images.
- **Strict Content Security Policy (CSP)**: Enforced via production HTTP headers with `'self'` only (zero `'unsafe-inline'`, zero `'unsafe-eval'`, `frame-ancestors 'none'`).
- **Optional Local Storage**: Saving an assessment is strictly opt-in. Unsaved assessments run in-memory and produce zero database records. Opted-in records are encrypted locally with SQLCipher (AES-256) and strictly scoped to the anonymous browser session.
- **Decentralized Offline Sharing**: Results can be exported via self-contained URL fragments (`#report=` for unencrypted base64url or `#encrypted=v1.<salt>.<iv>.<ciphertext>` with client-side WebCrypto AES-256-GCM and PBKDF2 310,000 iterations). Per RFC 3986, URL fragments are processed purely within the client's browser and are never transmitted in HTTP requests to Flask.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python test_clinical_system.py
python test_privacy_hardening.py
python verify_browser_behavior.py
python app.py
```

Open `http://127.0.0.1:5000`. For Waitress, run `python wsgi.py`; Waitress binds strictly to `127.0.0.1` and `PORT` defaults to `5000`.

## Docker

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f
docker compose down
```

The Dockerfile is single-stage, based on `python:3.11-slim`, runs as `appuser`, exposes the Render-provided port on `0.0.0.0`, persists the database under `/var/lib/diabeates`, and checks `/health`.

## Render Deployment

Deploy the Dockerfile as a Render Web Service with one persistent disk mounted at `/var/lib/diabeates`. The image binds Waitress to `0.0.0.0` and stores the SQLCipher database on that disk. Configure these Render environment variables:

```text
DEBUG=False
SECRET_KEY=<unique production secret>
DIABEATES_DB_KEY=<unique database encryption key>
DIABEATES_DATA_DIR=/var/lib/diabeates
SESSION_COOKIE_SECURE=True
```

Render supplies `PORT` automatically. Set the health check path to `/health`. Keep the service at one instance while it uses SQLite; multiple instances require moving storage to a shared database service.

## Health Endpoint

`GET /health` returns HTTP 200 only when SQLite is reachable and all four expected model files load. Otherwise it returns HTTP 503 with `status: degraded`. The response includes `database`, `models_loaded`, `models_expected`, and `rule_version`.

## Routes

`GET /`, `GET /assessment`, `POST /predict`, `GET /report`, `GET /about`, `GET /health`, `GET /history`, `POST /history/export`, `POST /history/clear`, `GET /history/<id>`, `GET /history/<id>/print`, `POST /history/<id>/archive`, `POST /history/<id>/delete`, `POST /feedback/<id>`, `GET /data/backup`, `POST /data/restore`, and `GET /diagnostics/export`.

## Important Files

- `app.py`: routes, model loading, sessions, CSRF, rate limits, strict CSP headers, logging, and retention.
- `rule_matrix.py`: version `2.0-clinical` rule scores and optional lab assessment.
- `clinical_model.py`: model wrapper and dual-threshold labels.
- `train_model.py`: training, calibration, evaluation, threshold selection, and artifact generation.
- `database.py`: SQLCipher encrypted storage, WAL mode, session isolation, safe migrations, backup/restore, feedback, and pruning.
- `validation.py`: server-side bounds checking.
- `static/js/`: client-side vanilla scripts (`app.js`, `assessment.js`, `history.js`, `print.js`, `result.js`, `report_viewer.js`).
- `static/css/`: compiled local Tailwind CSS (`tailwind.min.css`) and print stylesheet (`print.css`).
- `model/`: active models, summary, and plots.
- `data/`: source and processed cohort CSV files.

See [ARCHITECTURE.md](ARCHITECTURE.md), [METHODOLOGY.md](METHODOLOGY.md), [SECURITY.md](SECURITY.md), and [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md).
