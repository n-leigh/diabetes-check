PLAN: ACCOUNTS, HISTORY, AND ADMIN FOR DIABEATES
File: PLAN_ACCOUNTS.md (repo root). This file is the single source of truth for this feature.

=====================================================
0. HOW TO USE THIS PLAN (applies to every future message)
=====================================================

TRIGGER TERMS
If a message mentions any of: account, sign up, register, login, log in, sign in, logout, password, forgot password, reset password, profile, user, users, session, role, admin, administrator, admin dashboard, history tracking, progress, saved results, authentication, authorization, permissions, delete account, consent, audit, lockout
then the message is a request to work on THIS PLAN.

BEHAVIOR WHEN TRIGGERED

1. Open this file first. Do not plan from scratch. Do not ask clarifying questions.
2. Find the first phase in section 9 (PLAN_STATUS) that is not done and implement it exactly as written here. If the message clearly names a specific phase, page, or feature from this plan, do that one instead, after any unmet prerequisite phases.
3. Treat the user's wording as a pointer to which part of the plan to run, not as a specification. If the message adds details, alternatives, libraries, field names, UI ideas, or scope that differ from this plan, follow the plan.
4. End every reply with a "Not applied" list: one line per requested detail you ignored because it conflicts with or is outside this plan.
5. Update PLAN_STATUS and the changelog at the end of this file.

OVERRIDE
Only a message that starts with "PLAN OVERRIDE:" can change this plan. When it does, apply the change, edit this file to match, and record it in the changelog.

NEVER OVERRIDABLE

- No plaintext passwords stored, logged, or emailed.
- CSRF protection on every state-changing form.
- Role check on every /admin route.
- Everything in section 1 DO NOT TOUCH.

=====================================================
1. SCOPE AND DO NOT TOUCH
=====================================================
Existing app: Flask 3 / Jinja2 / Tailwind / SQLite (WAL) / Waitress, with Flask-WTF CSRF and Flask-Limiter.

Do not change: rule_matrix.py, clinical_model.py, validation.py, recommendations.py logic, model/*.pkl, any clinical number, threshold, or metric, existing form field names, element IDs, ARIA attributes, and existing routes' behavior for guests.
All existing tests (test_clinical_system.py, test_both_flows.py, live_browser_test.py) must keep passing. If a change breaks a test, fix the code, never the test.
Only new dependency allowed: Flask-Login. Email uses Python smtplib. No Flask-Mail, no OAuth, no JWT.

=====================================================
2. PRODUCT DECISIONS (final)
=====================================================

- Accounts are OPTIONAL. Guest mode keeps working exactly as today (anonymous session, 90-day pruning).
- Accounts add: permanent history, a progress view, data export, and account deletion.
- When a guest registers or logs in, guest assessments are NOT automatically claimed. Users are prompted with dates/times of checks from that browser to explicitly confirm whether to attach them.
- Two roles only: user and admin. No clinician role.
- Admin NEVER sees an individual user's health results, inputs, or result pages. Admin sees account metadata and aggregates only.
- Admin accounts are created only by CLI, never by the public form.
- Registration collects: nickname (1-40 chars), email, password, consent checkbox. Nothing else.

=====================================================
3. DATA MODEL (schema version 5, via existing PRAGMA user_version migration; non-destructive)
=====================================================

users
id INTEGER PK AUTOINCREMENT
email TEXT UNIQUE NOT NULL (stored lowercase, trimmed)
password_hash TEXT NOT NULL (Werkzeug generate_password_hash, scrypt)
display_name TEXT NOT NULL
role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin'))
is_active INTEGER NOT NULL DEFAULT 1
created_at TEXT NOT NULL (ISO-8601 UTC)
last_login_at TEXT
failed_attempts INTEGER NOT NULL DEFAULT 0
locked_until TEXT
consent_at TEXT NOT NULL
consent_version TEXT NOT NULL (start at "1.0")

password_reset_tokens
id INTEGER PK AUTOINCREMENT
user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
token_hash TEXT NOT NULL (SHA-256 of the token; never store the raw token)
expires_at TEXT NOT NULL (60 minutes)
used_at TEXT

audit_log
id INTEGER PK AUTOINCREMENT
actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL (nullable, set NULL when that user is deleted)
action TEXT NOT NULL
target TEXT
ip TEXT
created_at TEXT NOT NULL
Actions to log: login_success, login_failed, lockout, logout, password_changed, password_reset_requested, password_reset_completed, account_deleted, admin_user_deactivated, admin_user_reactivated, admin_user_deleted, admin_reset_link_created, admin_backup_created.
Never put emails or health data in target. Use user ids. Prune audit_log rows older than 90 days at startup via prune_audit_logs().

assessments: ADD user_id INTEGER NULL REFERENCES users(id) ON DELETE CASCADE. Keep session_id NOT NULL.
Indexes: users(email), assessments(user_id, archived, id), password_reset_tokens(token_hash), audit_log(created_at).

DELETIONS & FOREIGN KEYS:
The v4 child tables (risk_results, lab_assessments, feedback) have no ON DELETE CASCADE in their original CREATE TABLE statements, and SQLite cannot alter existing tables to add CASCADE. Do not rely on native cascade for existing child tables.
- Add one central helper in database.py: delete_assessments(where_clause, params) that executes within a single atomic transaction:
  DELETE FROM feedback WHERE assessment_id IN (SELECT id FROM assessments WHERE ...)
  DELETE FROM lab_assessments WHERE assessment_id IN (SELECT id FROM assessments WHERE ...)
  DELETE FROM risk_results WHERE assessment_id IN (SELECT id FROM assessments WHERE ...)
  DELETE FROM assessments WHERE ...
  Roll back on any error.
- delete_user_account(user_id) uses delete_assessments("user_id = ?", (user_id,)), deletes password_reset_tokens WHERE user_id = ?, and deletes the user from users.
- Route ALL deletions through delete_assessments: account deletion, single assessment deletion (/history/<id>/delete), and prune_expired_assessments.
- Keep PRAGMA foreign_keys=ON on every connection. Retention: prune_expired_assessments only deletes rows WHERE user_id IS NULL and older than retention cutoff.

=====================================================
4. ROUTES & OWNERSHIP
=====================================================

Public:
- GET/POST /register
- GET/POST /login
- GET/POST /forgot-password
- GET/POST /reset-password/<token>
- GET /privacy
- GET/POST /claim (explicit confirmation prompt for guest assessments)

Logged in:
- POST /logout
- GET /account
- POST /account/profile
- POST /account/password
- POST /account/delete
- GET /account/export (JSON download)
- GET /history/progress

Existing routes reading or modifying assessments:
- GET /history
- GET /history/<int:assessment_id>
- GET /history/<int:assessment_id>/print
- POST /history/<int:assessment_id>/archive
- POST /history/<int:assessment_id>/delete
- POST /feedback/<int:assessment_id>

OWNERSHIP RULE (Section 5.7):
Every route that reads or changes an assessment enforces strict ownership:
- Logged-in user: assessments.user_id == current_user.id.
- Guest user: assessments.session_id == session['session_id'] AND assessments.user_id IS NULL.
- If not owned, return 404 (not redirect). Admins get NO exception.

Admin only:
- GET /admin
- GET /admin/users
- POST /admin/users/<id>/deactivate
- POST /admin/users/<id>/reactivate
- POST /admin/users/<id>/delete
- POST /admin/users/<id>/reset-link
- GET /admin/feedback
- GET /admin/audit
- GET /admin/system
- POST /admin/system/backup
- GET /admin/export.csv

CLI: flask create-admin (prompts for email, nickname, password; refuses if email exists).

=====================================================
5. AUTH SPECS
=====================================================

5.1 Passwords: minimum 8 characters, maximum 128, reject a bundled list of the 100 most common passwords and any password equal to the email. Hash with scrypt. Confirm-password field on register and change-password.

5.2 Login: use Flask-Login. Look up by lowercase email. If the user does not exist, still run a dummy hash check so timing matches. One generic error for every failure: "Email or password is incorrect." Never reveal whether an email exists.

5.3 Lockout: after 5 consecutive failed logins, set locked_until = now + 15 minutes. Locked message: "Too many tries. Please wait 15 minutes and try again." Reset failed_attempts on success. Inactive accounts get the same generic error.

5.4 Rate limits (Flask-Limiter):
- Login: 10 per minute per IP.
- Register: 10 per hour per IP.
- Forgot-password: 5 per hour per IP.

5.5 Session, Cookies, and Guest Claim:
- Session: Before session.clear() on login or register, capture the current guest session id and store it in the new session as claim_sid.
- No automatic claiming in login/register handlers.
- After login or register, if claim_sid has unclaimed assessments (user_id IS NULL), redirect to /claim:
  "We found N check(s) from this browser. Save them to your account?" listing only the date and time of each, never results.
  Buttons: "Yes, save them" (POST /claim, action=confirm) and "No, leave them" (POST /claim, action=decline).
  - Yes runs: UPDATE assessments SET user_id=? WHERE session_id=? AND user_id IS NULL.
  - No leaves them as guest data.
  Either choice clears claim_sid from the session.
- Session ID on Insert: assessments.session_id remains NOT NULL. ensure_session_id() ensures a fresh UUID exists after session.clear(). save_assessment writes both user_id (if authenticated) and session_id.
- Cookies: Configured via env var COOKIE_SECURE (default False). SESSION_COOKIE_SECURE and REMEMBER_COOKIE_SECURE read from COOKIE_SECURE (set True when served over HTTPS). SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax" stay always on.
- Session protection: login_manager.session_protection = "basic" (mobile users change cellular IPs frequently).
- Remember me: 7 days for users. Admin role CANNOT use "keep me signed in"; ignore remember=True if user.role == 'admin'. Admin sessions expire after 30 minutes of inactivity (enforced in before_request).

5.6 Redirects: honor ?next= only if it is a relative path on this site. Otherwise go to /history.

5.7 Ownership: See section 4. Every route reading/changing an assessment checks ownership. Logged-in: user_id == current_user.id. Guest: session_id == session['session_id'] AND user_id IS NULL. Otherwise 404.

5.8 Password reset: always show "If that email has an account, we sent a link." Token = secrets.token_urlsafe(32), stored hashed with SHA-256, valid 60 minutes, single use, invalidates all other open tokens for that user. After reset, clear failed_attempts and lockout. Email via smtplib using env vars SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, BASE_URL (add to .env.example).
If SMTP is not configured:
- In debug, log the link to the console.
- In production, show configured text from env var ADMIN_CONTACT_TEXT, defaulting to: "Password reset by email is not set up. Please ask the site administrator to reset your password." Admin can generate a 60-minute reset link via the admin panel.

5.9 Account deletion: requires current password. Deletes the user via delete_user_account(user_id) which uses delete_assessments to atomically wipe all assessments, risk_results, lab_assessments, feedback, reset tokens, and user row. Writes account_deleted audit log with user id. Clears session and shows short confirmation.

5.10 Data export: JSON with user's nickname, email, and all their assessments, risk results, and lab values. Logged-in owner only.

5.11 Consent: registration blocked unless consent checkbox is checked. Store consent_at and consent_version. /privacy explains what is stored (email, nickname, assessments), why (history tracking), retention (guests 90 days, accounts until deleted), and data subject rights under RA 10173.

=====================================================
6. ADMIN SPECS
=====================================================

- Decorator admin_required: must be authenticated, role == 'admin', is_active. Otherwise 403. Applied to every /admin route.
- Dashboard: total users, new users in last 7 days, total assessments, assessments per day (last 30 days, simple CSS bar chart, no JS chart library), status distribution per complication (Good / Check / See a doctor, using the shared status helper), feedback helpful rate. Any aggregate cell with fewer than 5 records is displayed as "<5".
- Users: table with nickname, email, role, status, created, last login. Actions: deactivate, reactivate, delete, create reset link (shown once to the admin, valid 60 minutes). NO health data columns. An admin cannot deactivate or delete themselves, and the last active admin cannot be deactivated or deleted. Every action asks for confirmation and writes to audit_log.
- Feedback: list of helpful flag, comment, and date, with no link to the assessment or user.
- Audit: paginated audit_log, filterable by action.
- System: /health result, loaded model versions from training_summary.json, database size, current retention setting, "Create backup" button (writes a zip to backups/ like existing ones) and list of existing backups.
- Export: aggregate-only CSV (the dashboard numbers). Never row-level data.

=====================================================
7. UI AND COPY
=====================================================

Use the existing DiaBeates design system: plain language at grade 6, cream/sand bands, Fraunces headings, Source Sans 3 at 18px+, teal primary buttons, 48px tap targets, visible focus rings, role="alert" and aria-live on form errors, no jargon, no gradients or glow.

Shared Status Helper:
risk_results stores Low/Moderate/High. Do not add a database column. Create one shared helper function (get_status_presentation(rule_label)) that maps:
- Low -> Good (green badge & icon)
- Moderate -> Check (amber badge & icon)
- High -> See a doctor (rose badge & icon)
Used consistently across result page, history icons, progress view, and admin aggregates.

Navigation: Check, History, About, then "Sign in" (guest) or the nickname with an Account dropdown menu (logged in). Admin sees an "Admin" link. Mobile-first and keyboard-operable.

Copy:
- Register: heading "Save your checks"; line "Free. We only ask for your email."; fields "Nickname", "Email", "Password (at least 8 characters)", "Confirm password"; consent "I agree to the Privacy Notice. I understand my results are saved to my account."; button "Create account"; link "Already have an account? Sign in."
- Login: heading "Welcome back"; button "Sign in"; links "Forgot your password?" and "New here? Create an account."
- Forgot: heading "Reset your password"; line "We will email you a link."; button "Send link"
- Reset: heading "Choose a new password"; button "Save new password"
- History for guests shows calm banner: "Want to keep your checks? Create a free account." with button linking to /register.
- Account: sections "Your details", "Change password", "Download my data", "Delete my account". Delete warning: "This permanently deletes your account and all your saved checks. This cannot be undone." Button: "Delete my account".
- Progress view: for each of Heart, Kidneys, Nerves and feet, Eyes, show status words over time, newest on the right, with the same status icons and colors as results page, and one plain line such as "Kidneys: Check in March, Good in September." Show empty state with friendly illustration if fewer than 2 checks.
- Update home reassurance line to: "You can use DiaBeates without an account. If you make one, we only ask for your email."
- Update About page privacy text: describe optional accounts, roles, retention (guests 90 days, accounts until deleted), and Data Privacy Act of 2012 compliance.

=====================================================
8. PHASES (implement in order; each phase ends with all tests passing)
=====================================================

P1 Database: schema v5 migration, users / password_reset_tokens / audit_log tables, assessments.user_id, central delete_assessments helper, delete_user_account, prune_expired_assessments refactor, database.py helpers (create_user, get_user_by_email, get_user_by_id, update_password, set_lock, log_audit, prune_audit_logs), foreign keys on. Done when: migration is idempotent, old data is intact, zero orphan rows remain after deletions, existing tests pass.
P2 Auth core: Flask-Login setup, /register, /login, /logout, /privacy, consent, lockout, rate limits (10/min login), COOKIE_SECURE settings, nav changes, audit logging. Done when: user can register, log out, log in, with generic errors and lockout.
P3 History linkage & Claim: save_assessment stores user_id and session_id, /claim prompt flow with explicit Yes/No confirmation, ownership checks on all assessment routes, /history for users vs guests, guest banner. Done when: guest claim prompt works on login, declined checks stay guest data, and cross-user assessment access returns 404.
P4 Account management: /account, profile edit, change password, delete account via delete_user_account, JSON export, forgot/reset password with 60-min token and ADMIN_CONTACT_TEXT fallback.
P5 Progress view: /history/progress using the shared status helper and plain progress sentences.
P6 Admin: flask create-admin, admin_required, dashboard with <5 suppression, users table, feedback list, audit view, system view, CSV export, last-admin protection, admin idle timeout, remember-me block.
P7 Copy and docs: home and About copy updates, .env.example, README notes.
P8 Tests and wrap-up: write test_auth.py covering all authentication, ownership, deletion, and security invariants; run all suites.

=====================================================
9. TESTS (test_auth.py must cover)
=====================================================

- register success, duplicate email, weak password, missing consent
- login success, generic error for wrong password and unknown email, lockout after 5 failures and unlock after window, inactive user blocked
- rate limit: 11th login attempt within a minute from same IP returns 429
- open-redirect attempt via ?next= is rejected
- guest claim: after login/register, prompt is shown; confirming Yes claims assessments; declining No leaves assessments as guest data with user_id NULL
- shared device: user B logging in on browser with user A's guest checks sees claim prompt, can decline without claiming user A's checks
- ownership enforcement: user A cannot open, print, archive, delete, or give feedback on user B's assessment (returns 404)
- orphan-row verification: running delete_assessment, delete_user_account, and prune_expired_assessments leaves ZERO orphan rows in risk_results, lab_assessments, or feedback
- password reset: token valid for 60 minutes, single-use, expires, invalidates prior tokens, same response for unknown email; fallback text displayed when SMTP not configured
- admin remember-me block: admin user cannot set remember cookie
- account deletion: wipes user, assessments, and all child records; writes audit row with actor ID
- JSON export contains only owner's data
- non-admin gets 403 on every /admin route; anonymous redirected to login
- admin cannot delete self or last admin; admin pages never expose assessment inputs or results
- aggregates under 5 show "<5"
- single shared status helper returns correct triage badge and label for Low, Moderate, High
- existing guest flow in test_both_flows.py and test_clinical_system.py still passes unchanged
- CSRF enforced on every new POST

PLAN_STATUS
P1 [x] P2 [x] P3 [x] P4 [x] P5 [x] P6 [x] P7 [x] P8 [x]

CHANGELOG
- 2026-10-07: Completed P8 authentication and security verification. Added focused coverage for registration, generic login failures, lockout state, open-redirect rejection, guest claim decisions, ownership 404s including feedback, owner-only export and progress, single-use hashed password reset tokens, admin authorization, last-admin protection, and shared status mapping. All required clinical, flow, live browser, syntax, diagnostics, and whitespace checks passed. Final audit found no unapplied P1-P8 requirements.
- 2026-10-07: Completed P7 copy and documentation. Updated home reassurance, About privacy and retention text, README account/setup/admin guidance, route documentation, and environment-variable instructions. All required regression suites passed.
- 2026-10-07: Completed P6 admin tools. Added role-checked admin decorator, aggregate dashboard with under-five suppression, privacy-safe users/feedback/audit/system views, protected user actions with last-admin safeguards, one-time reset links, encrypted database backups, aggregate CSV export, admin navigation, and flask create-admin CLI. Admin smoke checks and all required regression suites passed.
- 2026-10-07: Completed P5 progress view. Added the shared Low/Moderate/High to Good/Check/See a doctor presentation helper, authenticated /history/progress route, newest-right timeline cards for all four domains, plain progress sentences, and a friendly two-check empty state. P4 audit remained clean, P5 smoke checks and all required regression suites passed.
- 2026-10-07: Completed P4 account management. Added account profile, password change, owner-only JSON export, password deletion with atomic data cleanup, 60-minute single-use reset tokens, SMTP delivery, debug-link logging, and production fallback contact text. P4 smoke checks and all required regression suites passed.
- 2026-10-07: Re-audited P1 and P2, then completed P3 history linkage and claim flow. Authenticated saves now record user ownership, history/detail/print/archive/delete enforce owner-or-guest-session access with 404 responses, guest history remains session-scoped, and registration/login offer an explicit date-only claim prompt with Yes/No confirmation. Required regression suites and claim/cross-user smoke checks passed.
- 2026-10-07: Completed P2 auth core. Added Flask-Login with basic session protection, optional secure/remember cookies, registration consent and password validation, generic login failures with five-attempt lockout, IP rate limits, CSRF-protected login/logout forms, privacy notice, admin idle timeout, audit logging, and signed-in navigation. Required clinical, flow, and live browser suites passed; registration/login smoke checks passed.
- 2026-10-07: Completed P1 database foundation. Added idempotent schema version 5 migration with users, password reset tokens, audit log, feedback, assessment ownership, indexes, password/account helpers, audit pruning, and centralized atomic assessment/account deletion. Guest-only retention pruning preserves account-owned assessments. Required clinical, flow, and live browser suites passed.
- 2026-10-01 (PLAN OVERRIDE):
  1. Routes (Section 4): Enumerated exact app.py routes (/history, /history/<id>, /history/<id>/print, /history/<id>/archive, /history/<id>/delete, /feedback/<id>) and mandated 404 ownership checks across all of them.
  2. Deletion (Section 3 & 5.9): Replaced SQLite CASCADE assumptions on v4 child tables with centralized delete_assessments helper and delete_user_account running inside atomic transactions. Added orphan-row verification.
  3. Guest Claim (Section 5.5 & P3): Replaced auto-claim with explicit confirmation prompt (/claim) showing dates/times only. Choosing No preserves checks as guest data.
  4. Session ID on Insert (Section 3 & 5.5): Required session_id to remain NOT NULL and populated for both guest and authenticated assessments.
  5. Status Words (Section 7): Established single shared helper mapping Low/Moderate/High to Good/Check/See a doctor without schema changes. Updated progress copy example.
  6. Cookies (Section 5.5): Introduced COOKIE_SECURE env var, set session protection to 'basic', and barred admin role from remember-me persistence.
  7. Rate Limits (Section 5.4): Increased login rate limit to 10 per minute per IP while keeping 5-failure lockout.
  8. Password Reset (Section 5.8): Extended token lifetime to 60 minutes and added ADMIN_CONTACT_TEXT fallback when SMTP is unconfigured.
  9. AGENTS.md Authorization: Authorized additive changes for P1-P8 while locking clinical and ML prediction logic. Added trigger rule for account-related prompts.
  10. Test Invariants (Section 9): Expanded test requirements to cover explicit claim, shared-device case, orphan cleanup, 60-min tokens, admin remember-me block, and shared status helper.

=====================================================
10. FINAL SUMMARY FORMAT (after each phase)
=====================================================
Phase completed, files changed, migrations applied, tests run and results, decisions made without asking, and the "Not applied" list.
