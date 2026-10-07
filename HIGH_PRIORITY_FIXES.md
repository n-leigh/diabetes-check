# High-Priority Operational Notes

This is a deployment-focused checklist, not a claim that every production concern is solved.

## Required Before Deployment

1. Set a strong `SECRET_KEY` in the deployment environment.
2. Keep `DEBUG=False`.
3. Use HTTPS and set `SESSION_COOKIE_SECURE=True`.
4. Restrict database, `.secret_key`, logs, and model permissions.
5. Confirm all four model artifacts load through `/health`.
6. Test backup, restore, retention, and reverse-proxy behavior.

## Implemented Controls

- Global CSRF protection and per-address rate limits of 300/day and 100/hour.
- Server-side validation and session-scoped history reads.
- SQLCipher AES-256 encrypted SQLite storage with WAL mode, foreign keys, busy timeout, and DPAPI key management.
- In-memory anonymous processing by default, with client-side WebCrypto encrypted URL hash sharing.
- Unified strict security headers: `X-Frame-Options: DENY`, `frame-ancestors 'none'`, and hardened Content Security Policy (`'self'` only, zero `'unsafe-inline'`, zero `'unsafe-eval'`).
- Rotating logs, generic user-facing errors, non-root Docker execution, and a health probe.

## Caveats

Compose supplies no secret, TLS, or secure-cookie configuration by default; production deployments must supply a strong `SECRET_KEY`, configure reverse-proxy TLS termination, and set `SESSION_COOKIE_SECURE=True`. Model metrics represent population cohort results, not individual clinical diagnoses or 10-year prospective risk guarantees.
