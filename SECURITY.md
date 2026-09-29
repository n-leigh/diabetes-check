# Security and Operations

## Configuration

| Variable | Default | Use |
|---|---|---|
| `SECRET_KEY` | generated and persisted to `.secret_key` when absent | Flask session signing |
| `DEBUG` | `False` | Flask debug behavior |
| `SESSION_COOKIE_SECURE` | `False` | HTTPS-only session cookies when true |
| `DISPLAY_TIMEZONE` | `Asia/Manila` | History timestamp display |
| `RETENTION_DAYS` | `90` | Startup data-pruning horizon |
| `PORT` | `5000` | Waitress port |
| `DIABEATES_DB_KEY` | *(optional)* | Hex key override for managed SQLCipher database deployments |
| `NHANES_RETINOPATHY_DIR` | `data/raw_retinopathy` | Raw XPT cache path for the retinopathy pipeline |

Set a unique production secret with `python -c "import secrets; print(secrets.token_hex(32))"`. The repository contains `.env.example`, not a committed `.env`. Set `SESSION_COOKIE_SECURE=True` when HTTPS is active.

## Controls

- Flask-WTF provides global CSRF protection for state-changing requests (including `/predict`, `/history/<id>/archive`, and `/history/<id>/delete`).
- Flask-Limiter applies `300 per day` and `100 per hour` by remote address; `/health` is exempt.
- `validation.py` revalidates every submitted field on the server.
- Assessment reads, archival mutations, and deletions are strictly filtered by an anonymous session UUID.
- Assessments are processed in-memory by default and persisted to the local encrypted database only when explicitly opted in by the user.
- Unexpected exceptions are logged with stack traces while users receive generic errors.
- SQLCipher uses foreign keys, WAL mode, and a busy timeout; the database key is protected with Windows DPAPI for local Windows deployments.
- Startup pruning uses `RETENTION_DAYS`; archive is soft state and delete is permanent.
- Logs rotate at 10 MB with five backups in `logs/diabetes_system.log`.

## Headers & Content Security Policy

The application sets strict production security headers via a unified `@app.after_request` handler:
- `X-Frame-Options`: `DENY`
- `X-Content-Type-Options`: `nosniff`
- `X-XSS-Protection`: `1; mode=block`
- `Referrer-Policy`: `strict-origin-when-cross-origin`
- `Permissions-Policy`: `geolocation=(), microphone=(), camera=()`
- Strict Content Security Policy (`default-src 'self'`, `script-src 'self'`, `style-src 'self'`, `img-src 'self' data:`, `font-src 'self'`, `connect-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`).
  - **Zero `'unsafe-inline'`** across all scripts and styles.
  - **Zero `'unsafe-eval'`**.
  - **Zero external CDN, remote font, or remote image dependencies**.
- `Strict-Transport-Security`: `max-age=31536000; includeSubDomains` (when `DEBUG=False`).
- `Cache-Control`: `no-store, no-cache, must-revalidate, max-age=0` (on sensitive clinical routes).

## Deployment

The Docker image is single-stage, based on `python:3.11-slim`, runs as non-root `appuser`, exposes port 5000 bound strictly to `127.0.0.1:5000`, and checks `/health`. Compose mounts the database, database keys, and log directory; supply secrets, TLS, and secure-cookie settings separately.

## Pre-Production Checklist

- Set a unique `SECRET_KEY` outside source control.
- Keep `DEBUG=False` and enable `SESSION_COOKIE_SECURE` with HTTPS.
- Restrict database, `.secret_key`, logs, and model permissions.
- Confirm `/health` returns 200 with all four models loaded.
- Confirm strict CSP (`'self'` only, zero `'unsafe-inline'`) is active.
- Verify localhost binding on port 5000 (`127.0.0.1:5000`).
- Test retention, archiving, and single-record deletion procedures.
- Run `python test_clinical_system.py`, `python test_privacy_hardening.py`, and `python verify_browser_behavior.py` after deployment changes.

## Security Architecture Decisions

The following explicit tradeoffs and decisions define the security boundaries of the system:

- **SQLCipher Driver & Engine**: The application interfaces via the `sqlcipher3` Python driver backed by a native SQLCipher 4 engine (verified via `PRAGMA cipher_version`), providing 256-bit AES encryption in WAL mode.
- **Audit Trails vs. Anonymity**: We accept no audit trail. The system is intentionally anonymous-by-default, explicitly trading clinical auditability ("who saw what, when") for maximum patient privacy.
