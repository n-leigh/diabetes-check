# Security, Operations & Configuration Guide

## Overview

This document outlines security controls, defensive countermeasures, operational configurations, and deployment architectures implemented for the Diabetes Complication Prediction System (**DiaBeates**).

---

## Configuration & Environment Management

### Environment Variables (`.env`)

Application secrets and deployment flags are configured via `.env`:

```bash
# Flask Session Security Key
SECRET_KEY=<generate-a-strong-random-hex-key>

# Deployment Mode (set False in production)
DEBUG=False

# Cookie Security (set True when HTTPS is enabled)
SESSION_COOKIE_SECURE=True

# Application Port
PORT=5000

# Display Timezone for Audit and History (default Asia/Manila / PHT)
DISPLAY_TIMEZONE=Asia/Manila
```

### Secret Key & Session Hardening

The `SECRET_KEY` cryptographically signs Flask session cookies to protect client-side session states:
- **Defense in Depth**:
  - `SESSION_COOKIE_HTTPONLY=True`: Prevents client-side scripts from reading session cookies, thwarting XSS session extraction.
  - `SESSION_COOKIE_SAMESITE="Lax"`: Mitigates Cross-Site Request Forgery (CSRF) on ambient browser requests.
  - `SESSION_COOKIE_SECURE`: Conditionally enforces HTTPS-only cookie transmission when running behind TLS.
  - `PERMANENT_SESSION_LIFETIME=86400`: Caps session lifespan to 24 hours.
  - **Startup Verification**: The application logs a high-severity alert if `DEFAULT_SECRET_KEY` is detected while `DEBUG=False`.

To generate a cryptographically strong secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Defensive Countermeasures & Security Headers

### 1. HTTP Security Headers
Every HTTP response is injected with defensive headers in `app.py`:
- `X-Frame-Options: DENY`: Blocks clickjacking attacks by forbidding iframe embedding.
- `X-Content-Type-Options: nosniff`: Prevents MIME-type sniffing vulnerabilities.
- `Referrer-Policy: strict-origin-when-cross-origin`: Restricts leaking sensitive URL parameters to third parties.
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`: Disables unneeded browser capabilities.
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`: Enforces HTTPS for all client communication in production.

### 2. Cross-Site Request Forgery (CSRF) Protection
- Implemented globally via **Flask-WTF** (`CSRFProtect(app)`).
- Every POST request (`/predict`, `/history/<id>/archive`, `/history/<id>/delete`) requires a valid CSRF token.
- Invalid or missing tokens trigger HTTP 400 Bad Request responses with audit log entries.

### 3. Rate Limiting
- Enforced via **Flask-Limiter** using client remote addresses (`get_remote_address`).
- Default limit: `300 per day`, `100 per hour` across public routes.
- Protects clinical triage endpoints against brute-force abuse and Denial of Service (DoS).

---

## Production Runtime & Containerization

### 1. Multi-Stage Docker Deployment
- **Base Image**: `python:3.11-slim` for minimal surface area and vulnerability reduction.
- **Unprivileged Execution**: Drops privileges to `appuser` (created without home directory and non-root UID).
- **Environment Isolation**: Bytecode caching disabled (`PYTHONDONTWRITEBYTECODE=1`), unbuffered logging enabled (`PYTHONUNBUFFERED=1`).
- **Volume Mounts**: Isolated persistent storage for `diabetes_system.db` and `/app/logs`.

### 2. Multi-Threaded WSGI Server (Waitress)
- Entrypoint [`wsgi.py`](wsgi.py) replaces development servers with production Waitress:
```python
serve(app, host='0.0.0.0', port=5000, threads=8)
```
- Provides stable concurrent connection handling without thread starvation.

### 3. Automated Liveness & Readiness Healthcheck (`/health`)
- Exposes an operational monitoring endpoint at `/health`.
- Verifies:
  1. Database read/write connectivity.
  2. All 4 clinical risk models (`cardiovascular`, `general_burden`, `neuropathy_mobility`, `retinopathy`) loaded in memory.
- Integrated into Docker container health probes (`HEALTHCHECK` in `Dockerfile`).

---

## Data Privacy, Storage & Retention

### 1. Anonymous Session Isolation
- Assessments are keyed to an anonymous UUID string stored in the user's session (`session["session_id"]`).
- No personally identifiable information (PII) such as patient names, emails, national IDs, or IP addresses are persisted in the assessment database.
- Database queries enforce strict `session_id` filtering, preventing cross-tenant record leakage.

### 2. Database Reliability (SQLite WAL Mode)
- Configured with `PRAGMA journal_mode = WAL` (Write-Ahead Logging).
- Allows concurrent readers while a single writer commits, preventing table locking.
- Safe, non-destructive schema migrations ensure columns (`diabetes_duration`, `blurry_vision`, `archived`) are added idempotently without data loss.

### 3. Automated Data Retention Pruning
- Implemented via `prune_expired_assessments(days=90)` in [`database.py`](database.py).
- Purges stale records and associated risk entries exceeding the retention horizon, complying with data minimization principles.

### 4. Patient Audit Trail & UX
- Assessment history supports chronological sorting (newest first / oldest first).
- Stable sequential display numbering (`#1`, `#2`, ...).
- Timestamps converted to localized Philippine Standard Time (PHT / UTC+8).
- Deletion operations protected with accessible modal dialogs that enforce keyboard focus trapping and explicit user confirmation.

---

## Input Validation & Bounds Checking

All inputs submitted to `/predict` are validated server-side in [`validation.py`](validation.py) before execution:

| Parameter | Allowed Range / Types | Validation Policy |
|---|:---:|---|
| **Age** | 1 – 13 (BRFSS age bands) | Integer bounds |
| **Sex** | 0 (Female), 1 (Male) | Binary integer |
| **BMI** | 10.0 – 80.0 | Floating-point range |
| **Diabetes Duration** | 0 – 4 (<1 yr, 1–5 yrs, 5–10 yrs, 10–20 yrs, 20+ yrs) | Categorical band |
| **HighBP / HighChol / Smoker / Stroke** | 0 or 1 | Binary integer |
| **HeartDiseaseorAttack / DiffWalk / BlurryVision** | 0 or 1 | Binary integer |
| **PhysHlth / MentHlth** | 0 – 30 days | Integer day bounds |
| **GenHlth** | 1 – 5 | Categorical integer |
| **NoDocbcCost** | 0 or 1 | Binary integer |
| **HbA1c (Optional)** | 3.0 – 20.0% | Optional floating-point |
| **Systolic BP (Optional)** | 60 – 250 mmHg | Optional integer |
| **LDL Cholesterol (Optional)** | 20 – 400 mg/dL | Optional integer |

---

## Logging & Auditing

- **Log File**: `logs/diabetes_system.log`
- **Rotation Policy**: Rotates at 10MB with 5 archived backups (50MB maximum ceiling).
- **Log Events**:
  - Application startup, configuration warnings, and loaded model summaries.
  - CSRF verification errors.
  - Validation failures and malformed payloads.
  - Model inference executions and database transaction status.

```bash
# View real-time logs on Windows PowerShell
Get-Content .\logs\diabetes_system.log -Tail 50 -Wait

# Search for security warnings or errors
Select-String "WARNING|ERROR|CSRF" .\logs\diabetes_system.log
```

---

## Production Security Checklist

- [x] CSRF protection enabled across all form endpoints (Flask-WTF)
- [x] Server-side bounds checking for all 15 clinical indicators and optional lab values
- [x] Multi-stage Docker container build running as non-root user (`appuser`)
- [x] Multi-threaded production WSGI server via Waitress (`wsgi.py`)
- [x] Operational health check probe (`/health`)
- [x] Defensive HTTP security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `HSTS`)
- [x] Rate limiting on public prediction endpoints (Flask-Limiter)
- [x] Automated 90-day data retention pruning (`prune_expired_assessments`)
- [x] Rotating file logger with 10MB limit and 5 backups
- [x] SQLite WAL mode enabled for concurrent performance and non-destructive migrations
- [ ] Set unique `SECRET_KEY` in production `.env`
- [ ] Set `DEBUG=False` in production `.env`
- [ ] Terminate TLS/HTTPS via reverse proxy (Nginx, Traefik, or Caddy)

