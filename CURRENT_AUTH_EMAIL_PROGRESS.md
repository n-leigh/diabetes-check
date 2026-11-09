# Current Login, Logout, and Email Verification Progress

Updated: 2026-11-08

This handoff is for the next AI agent working on DiaBeates. It describes the
current implementation and known blockers. No credentials or `.env` values are
included.

## Current branch and commits

- Branch: `feature/email-verification`
- Latest relevant commit: `4eb5366` (`Harden account email notifications`)
- The worktree may contain an unrelated modified log file:
  `logs/diabetes_system.log`. Do not commit it.

## Login flow

### Route

`POST /login` is implemented in `app.py`.

1. The submitted email is trimmed and lower-cased.
2. The user is loaded by normalized email.
3. A dummy password hash is checked when the email is unknown.
   This helps prevent account enumeration through timing differences.
4. Inactive users, bad passwords, and unknown users receive the same message:
   `Email or password is incorrect.`
5. After five failed attempts, an active account is locked for 15 minutes.
6. An already locked account receives a wait message.
7. An account with `email_verified_at` set to `NULL` is denied login with:
   `Please confirm your email first.`
8. The pending email is stored in the session so the login page can show a
   resend-confirmation button.
9. A successful login:
   - preserves the guest session ID for the claim flow;
   - clears and regenerates the session;
   - records `last_login_at`;
   - calls Flask-Login `login_user`;
   - does not remember admin sessions;
   - writes a `login_success` audit event;
   - redirects through the existing safe post-auth redirect helper.

Relevant code: [`app.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/app.py:699)

## Logout flow

### Route

`POST /logout` is protected by `@login_required`.

1. The current user ID is captured for audit logging.
2. Flask-Login logs the user out.
3. The session is cleared.
4. The remember-me action is preserved if Flask-Login placed it in the
   session.
5. A `logout` audit event is written.
6. The user is redirected to `/`.

Logout is submitted by forms in the account menu and includes the CSRF token.
There is no GET logout route.

Relevant code: [`app.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/app.py:806)

## Registration and email verification

### Registration

`POST /register`:

1. Normalizes the email to lowercase.
2. Validates nickname, email, password, confirmation, and privacy consent.
3. If forced verification is enabled but SMTP is incomplete, registration is
   disabled with a friendly error.
4. A verified existing account receives the generic already-registered error.
5. An existing unverified account is replaced with the new nickname/password,
   reset to unverified, and receives a new token.
6. A new account is:
   - unverified when SMTP is configured and verification is required;
   - automatically verified only when verification is not required.
7. Verification tokens are generated with `secrets.token_urlsafe`, stored as
   SHA-256 hashes, and expire after 24 hours.
8. The raw token is used only in the email link.
9. Successful pending registration redirects to `/check-email`.

Relevant code: [`app.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/app.py:627)

### Verification link behavior

Route: `/verify-email/<token>`.

- `GET` validates the hashed token but does not consume it.
- `GET` shows:
  - confirmation form for a valid unused token;
  - already-confirmed state for a previously verified account;
  - invalid/expired state for an invalid token.
- `POST` consumes the token atomically and sets `email_verified_at`.
- A token cannot be reused.
- A welcome email is attempted after successful verification.
- Welcome-email failure does not undo verification.
- Invalid and expired links do not reveal account details.

Relevant code: [`app.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/app.py:780)

### Resend behavior

`POST /resend-verification`:

- Requires CSRF.
- Is limited to five requests per hour by Flask-Limiter.
- Also has an in-memory per-email cooldown/history.
- Only sends for an existing unverified account.
- Stores only a hash of the replacement token.
- Returns a generic check-email page instead of revealing whether an email
  exists.

## Password reset relationship

- `POST /forgot-password` creates a hashed, single-use token with a 60-minute
  expiry and attempts delivery.
- The response is anti-enumeration oriented.
- `POST /reset-password/<token>` validates the token and password, changes the
  password, consumes the token, and marks the account email verified.
- A password-changed notification is sent asynchronously.

Relevant code:

- [`app.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/app.py:1187)
- [`database.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/database.py:835)

## SMTP status and current problem

The application uses SMTP with STARTTLS, normally on port `587`.

Required configuration names are:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `BASE_URL`

The real delivery test previously failed with `SMTPAuthenticationError`.
The likely cause is the Brevo credential pair, not website deployment:

- `SMTP_USER` must be the SMTP login shown in Brevo's **SMTP & API** area.
- `SMTP_PASSWORD` must be an SMTP key.
- The login may be email-shaped. Email-shaped usernames are valid and must not
  be rejected based on their shape.
- Do not use a Brevo API key or the normal account password as the SMTP
  password.
- `SMTP_FROM` must be a verified sender in Brevo.

The diagnostic script currently supports:

```powershell
python scripts\send_test_email.py --check-auth-only
```

It must be run only after correcting the SMTP values. It authenticates without
sending an email. A real send should be one message to an explicitly supplied,
authorized recipient:

```powershell
python scripts\send_test_email.py --to recipient@example.test
```

Never paste or print the values from `.env`.

Relevant code:

- [`app.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/app.py:437)
- [`scripts/send_test_email.py`](C:/Users/carlo/Documents/htdocs/diabetes-check/scripts/send_test_email.py:1)

## Email templates and privacy

Templates exist for:

- verification;
- welcome;
- password reset;
- password changed;
- saved check;
- account deleted.

Account notification emails are opt-in. They do not include health results,
clinical scores, or assessment details.

## Tests already completed

Before the Postgres-only migration attempt:

- Full pytest run: `232 passed`.
- Clinical system suite: passed when explicitly isolated to temporary SQLite.
- Both clinical flows: passed.
- Focused template/CSP tests: `198 passed`.
- Password-reset email worker regression test: passed after adding Flask
  application context to asynchronous delivery.

Important limitation: these tests were run on temporary SQLite, not a
Postgres test database.

## Current Postgres blocker

The Postgres-only migration task has not started safely because no isolated
`TEST_DATABASE_URL` is configured, and neither Docker nor the Supabase CLI is
available in the environment.

The next agent must not:

- connect tests to `SUPABASE_DB_URL`;
- fall back to SQLite;
- run SQL against production;
- print or inspect secret values.

A throwaway Supabase project is required. Use its Session pooler connection
string on port `5432`, set `TEST_DATABASE_URL`, and set
`ALLOW_TEST_DB_RESET=1`. The test project must have a different host/project
reference from production.

## Recommended next actions

1. Configure a separate synthetic-data Supabase test project.
2. Add a guard in `conftest.py` that rejects missing, production, or
   same-host test URLs before any database connection.
3. Apply all repository migrations idempotently to the test database.
4. Run the authentication, clinical, browser, and Postgres-specific suites.
5. Fix Postgres-specific issues without changing clinical files.
6. Correct and re-run the Brevo SMTP auth-only diagnostic.
7. Only after Postgres tests pass, remove SQLite/SQLCipher from runtime.
8. Apply production SQL manually after a backup and explicit review.
