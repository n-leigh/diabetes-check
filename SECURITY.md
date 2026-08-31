# Security & Configuration Guide

## Overview

This document outlines security measures, configuration requirements, and deployment best practices for the Diabetes Complication Prediction System.

---

## Configuration Management

### Environment Variables (`.env`)

The `.env` file (created automatically) stores sensitive configuration:

```
SECRET_KEY=<random-secure-key>
DEBUG=false
```

**Critical Rules:**
- ✅ `.env` is in `.gitignore` — NEVER commit it to version control
- ✅ Each deployment environment needs its own `.env`
- ⚠️ **Before production:** Generate a new SECRET_KEY:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- ⚠️ **Before production:** Set `DEBUG=false`

### Secret Key Management

The `SECRET_KEY` protects Flask session cookies. If it's weak or leaked:
- Session hijacking becomes trivial
- Attackers can forge user identities
- Patient data history becomes accessible to unauthorized users

**Current Status:**
- ✅ Logging warns if default key is in use
- ✅ Logging warns if DEBUG mode is enabled
- ⚠️ **TODO for production:** Implement key rotation strategy

---

## Model Loading & Graceful Degradation

### Issue: Missing Model Files

If trained models (`model/*.pkl`) are missing, the app previously warned but still attempted predictions (causing silent failures).

**Fix Implemented:**
- ✅ Models are now loaded with try-catch error handling
- ✅ `MODELS_AVAILABLE` flag tracks success/failure
- ✅ Logs clearly indicate which models failed to load
- ✅ App gracefully falls back to rule-matrix-only predictions if models are unavailable
- ✅ Template can check `MODELS_AVAILABLE` to show/hide model predictions

**What to do if models are missing:**
```bash
python train_model.py     # Retrain models from data/diabetes_dataset.csv
```

---

## Logging & Audit Trails

### What's Logged

Logs are stored in `logs/diabetes_system.log` and also printed to console:

**Startup:**
- Application initialization status
- Debug mode enabled/disabled
- Models available/unavailable
- Schema version checks

**Per-Assessment:**
- Form validation failures
- Rule matrix computations
- Model predictions (with confidence scores)
- Any prediction errors

**Errors:**
- Full exception stack traces
- Validation failures
- Model inference failures
- Database errors

### Log Rotation

Logs are automatically rotated when `diabetes_system.log` exceeds 10MB (5 backup files kept).

### Viewing Logs

```bash
# Real-time (on Windows PowerShell)
Get-Content .\logs\diabetes_system.log -Tail 50 -Wait

# Search for errors
Select-String "ERROR" .\logs\diabetes_system.log
```

---

## Data Privacy

### Session Management

- ✅ Each visitor gets a unique session cookie (via `session["session_id"]`)
- ✅ History page filters by session — users ONLY see their own assessments
- ✅ Database enforces session_id checks on all history/archive/delete operations

**Database Schema:**
- `assessments.session_id` — anonymous visitor ID (not email, not username)
- `assessments.created_at` — timestamp in UTC ISO format
- All assessment data is tied to this session_id

### Data Retention

Currently:
- ✅ Users can manually delete assessments (soft/hard delete available)
- ✅ Users can archive assessments
- ⚠️ **TODO for production:** Implement automatic data retention policy (e.g., delete after 90 days)

### Database File

- ✅ `diabetes_system.db` is in `.gitignore` — won't be committed
- ⚠️ **Before production:** Set appropriate file permissions:
  ```bash
  # Linux/Mac:
  chmod 600 diabetes_system.db
  
  # Windows (admin terminal):
  icacls diabetes_system.db /inheritance:r /grant:r "%USERNAME%:F"
  ```

---

## Input Validation

### Server-Side Validation

All form inputs are validated on the server, regardless of client-side checks:

**Validated Fields:**
- BMI: 10.0–80.0 (float)
- Age: 1–13 BRFSS bands (int)
- General Health: 1–5 (int)
- Physical Health Days: 0–30 (int)
- Mental Health Days: 0–30 (int)
- Lab values (optional):
  - HbA1c: 3.0–20.0 (float)
  - Systolic BP: 60–250 (int)
  - LDL: 20–400 (int)
- Checkboxes: Binary (0 or 1)
- Selects: Allowed values only

**Error Handling:**
- ✅ All validation happens before prediction
- ✅ Errors are returned to the form page with user-friendly messages
- ✅ Invalid data is never saved to the database
- ✅ Malformed requests don't crash the app

---

## Exception Handling

**Before:** Unhandled exceptions would show Flask debug pages (leaking stack traces).

**After:**
- ✅ All exceptions caught by `@app.errorhandler(Exception)`
- ✅ Full stack trace logged to `logs/diabetes_system.log`
- ✅ User sees generic "Something went wrong" message (doesn't leak internals)

---

## Recommended Production Checklist

- [ ] Generate and set new `SECRET_KEY` in `.env`
- [ ] Set `DEBUG=false` in `.env`
- [ ] Run `python train_model.py` to generate fresh models
- [ ] Set database file permissions (600 on Linux/Mac, restricted on Windows)
- [ ] Configure a production WSGI server (gunicorn, Waitress, etc.) instead of Flask's development server
- [ ] Set up HTTPS/SSL certificate
- [ ] Configure a reverse proxy (nginx, Apache) with security headers:
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `Content-Security-Policy: default-src 'self'`
- [ ] Implement rate limiting on `/predict` endpoint
- [ ] Set up monitoring/alerting on `logs/diabetes_system.log` for ERROR entries
- [ ] Document data retention policy
- [ ] Test graceful degradation if models go offline (fallback to rule-matrix)
- [ ] Backup database regularly (don't rely on version control)

---

## Common Questions

**Q: Can I share my `.env` file with teammates?**  
A: No — use a `.env.example` template without actual keys. Each person generates their own.

**Q: What if I forget to change the SECRET_KEY?**  
A: ⚠️ Critical vulnerability. Any attacker can forge session cookies and access all patient histories.

**Q: What happens if the models crash during prediction?**  
A: Logged and caught. App returns rule-matrix results only. User sees "Model unavailable" indicator.

**Q: How long are logs kept?**  
A: 5 files × 10MB = 50MB max. Oldest logs are rotated out. For long-term audit trails, export logs periodically.

**Q: Can I disable logging in production?**  
A: Not recommended — logs are your only visibility into system health and errors.

---

## Questions for Your Defense

Be ready to explain:

1. **"How do you protect session data?"**  
   → By session_id, not username. History endpoint filters by session_id.

2. **"What if models fail?"**  
   → Graceful degradation: app continues with rule-matrix predictions only.

3. **"How do you handle invalid input?"**  
   → Server-side validation catches all violations before prediction.

4. **"Where are logs stored? How long?"**  
   → `logs/diabetes_system.log` with rotation at 10MB.

5. **"Is your SECRET_KEY secure for production?"**  
   → Not yet. Must be regenerated and set in `.env` before deployment.

6. **"What if the database file is leaked?"**  
   → Contains session_id (anonymous), timestamps, and predictions — no names, no emails. Still serious, but limited PII.

---

## References

- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Python Secrets Module](https://docs.python.org/3/library/secrets.html)
- [Flask Security](https://flask.palletsprojects.com/en/2.3.x/security/)
- [SQLite Security](https://www.sqlite.org/security.html)
