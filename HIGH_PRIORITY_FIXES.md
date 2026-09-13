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
- SQLite foreign keys, WAL mode, busy timeout, and additive schema initialization.
- Rotating logs, generic user-facing errors, non-root Docker execution, and a health probe.

## Caveats

The CSP permits inline/eval scripts and external HTTPS resources. The effective `X-Frame-Options` value is `SAMEORIGIN` because two hooks set it and the later one wins. Compose supplies no secret, TLS, or secure-cookie configuration by default. Model metrics are cohort results, not clinical validation.
