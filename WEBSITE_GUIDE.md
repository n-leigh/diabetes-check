# DiaBeates Website Guide

This guide explains the DiaBeates website as a whole. It is intended for
developers, reviewers, and AI assistants working on the repository.

## 1. Product summary

DiaBeates is a local Flask and Jinja2 web application for diabetes-complication
risk screening. It is a screening and discussion aid, not a diagnosis or
treatment system.

The assessment checks four areas:

1. Heart: cardiovascular risk
2. Kidneys: kidney-related risk
3. Nerves and feet: neuropathy and mobility risk
4. Eyes: retinopathy and vision risk

The application combines:

- A transparent clinical rule matrix.
- Four calibrated machine-learning models.
- Optional laboratory interpretation.
- Plain-language explanations and questions for a doctor.
- Optional saved history, progress tracking, accounts, and administration.

All patient-facing results must be reviewed with a qualified healthcare
professional.

## 2. Main navigation

The shared navigation is defined in [templates/base.html](templates/base.html).

- **Home**: introduction and entry point.
- **Check**: starts a new health risk assessment.
- **History**: shows saved checks owned by the current browser session or account.
- **About**: explains the method, limitations, privacy, and clinical scope.
- **Sign in / account avatar**: account access for optional account features.
- **Admin**: visible only to administrators.

The site is designed for mobile phones first, with clinic desktop use also
supported.

## 3. Public pages

### Home: `/`

Template: [templates/home.html](templates/home.html)

The home page introduces the service and provides the main **Start check**
action. It explains:

- The check takes about three minutes.
- Users answer 15 questions.
- Results cover the heart, kidneys, nerves and feet, and eyes.
- Results help users prepare questions for a doctor.
- Answers are private and the tool does not require a name or email to start.

### Assessment: `/assessment`

Template: [templates/assessment.html](templates/assessment.html)

The assessment is a three-step wizard using one form submitted to
`POST /predict`.

#### Step 1: About you

- Age range.
- Sex assigned at birth.
- BMI.
- General health rating.
- Diabetes duration.

The BMI field supports direct entry and an accessible BMI calculator modal.
The calculator supports metric and imperial units, live preview, validation,
and writes the calculated value back to the main BMI field.

#### Step 2: Your health

The form collects visual yes/no choices for:

- High blood pressure.
- High cholesterol.
- Smoking history.
- Heart disease or heart attack.
- Stroke history.
- Difficulty walking or climbing stairs.
- Blurry vision or eye issues.
- Skipped doctor visit because of cost.

It also collects physical-health and mental-health days over the last 30 days.

#### Step 3: Optional lab results

Users may provide:

- 3-month sugar test (HbA1c).
- Top blood pressure number (systolic BP).
- Bad cholesterol (LDL).

The form validates all inputs server-side before scoring. CSRF protection is
required on submission.

### Results: returned by `POST /predict`

Template: [templates/result.html](templates/result.html)

The results page displays:

- Overall triage summary.
- Four domain results.
- Plain-language status badges: Good, Check, or See a doctor.
- What the result means.
- Factors that affected the result.
- Questions to ask a doctor.
- Optional laboratory interpretation.
- Technical details for providers inside progressive-disclosure sections.
- Save, print, share/report, or start a new check actions where applicable.

The page can show both rule-matrix results and model estimates. These are
complementary signals and must not be presented as interchangeable diagnoses.

### About: `/about`

Template: [templates/about.html](templates/about.html)

The About page explains:

- Why early screening can help.
- Transparent rule-based scoring.
- Statistical classification models.
- Input validation and personalized guidance.
- Referral advisories.
- Dataset and clinical-target scope.
- Ethical limitations and the non-diagnostic disclaimer.

### Privacy: `/privacy`

Template: [templates/privacy.html](templates/privacy.html)

The Privacy page explains what account information and saved checks may be
stored. Guest users can use the screening flow without creating an account.

### Health readiness: `/health`

This endpoint returns JSON readiness information. It checks database
connectivity and whether all four expected model files loaded. It returns HTTP
200 when healthy and HTTP 503 when degraded.

## 4. History and progress

### History: `/history`

Template: [templates/history.html](templates/history.html)

History shows saved assessments in active or archived views. It includes:

- Philippine Time date and time.
- Chronological check number.
- BMI.
- Heart, kidney, nerves/feet, and eye status.
- View result action.
- Archive/restore action.
- Delete action.
- New check action.
- Check Progress action.

Only saved assessments appear. An assessment that is not saved remains
in-memory for its immediate result/print flow and does not become history.

### Progress tracker: `/history/progress`

Template: [templates/progress.html](templates/progress.html)

The tracker displays each domain as a timeline of saved results:

- Heart.
- Kidneys.
- Nerves and feet.
- Eyes.

At least **two saved checks in the same ownership scope** are needed to show
meaningful progress. With fewer than two, the page shows a prompt to keep
checking.

Ownership scope is important:

- Guest history uses the current browser session ID.
- Account history uses the signed-in user ID.
- Guest checks from another browser session are not merged automatically.
- Guest checks are not automatically attached to an account during login or
  registration; the user must confirm the claim flow.

The tracker supports both SQLite-style text timestamps and PostgreSQL datetime
values.

### Individual history result: `/history/<id>`

Shows the saved result for one owned assessment. It uses the same clinical
result presentation as the normal results page and includes patient-specific
risk drivers and recommendations.

### Saved printable result: `/history/<id>/print`

Template: [templates/print_result.html](templates/print_result.html)

Provides a print-focused medical summary for discussion with a healthcare
professional.

### Current-result print view: `/print/<print_id>`

This uses a short-lived in-memory token created during the current assessment.
It is not the same as a permanently saved history record.

## 5. Accounts and authentication

Accounts are optional. Guest screening remains available.

### Register: `GET/POST /register`

Template: [templates/register.html](templates/register.html)

Registration collects:

- Nickname.
- Email.
- Password.
- Privacy consent.

Passwords are stored as hashes, never plaintext. After registration, the
application may offer an explicit claim step for guest checks in the same
browser.

### Sign in: `GET/POST /login`

Template: [templates/login.html](templates/login.html)

Sign-in supports optional “Keep me signed in” behavior. Login redirects to the
requested safe local destination or the user's history.

### Sign out: `POST /logout`

Clears the authenticated login and session state. The request is CSRF
protected.

### Password recovery

- `GET/POST /forgot-password`
- `GET/POST /reset-password/<token>`

Reset tokens are single-use, time-limited, and stored hashed.

### Claim guest checks: `GET/POST /claim`

Template: [templates/claim.html](templates/claim.html)

After registration or login, the user can explicitly decide whether to attach
unclaimed guest checks from the same browser session to the account.

### Account: `/account`

Template: [templates/account.html](templates/account.html)

Signed-in users can:

- Update their nickname.
- Change their password.
- Download their account data as JSON.
- Permanently delete their account and owned saved checks.

## 6. Administration

Admin pages are restricted to users with the administrator role. Admins do not
get access to individual patient inputs or result pages.

### Admin dashboard: `/admin`

Template: [templates/admin_dashboard.html](templates/admin_dashboard.html)

Shows safe aggregate service information, such as account totals, assessment
totals, status counts, feedback summaries, and checks per day.

### Accounts: `/admin/users`

Template: [templates/admin_users.html](templates/admin_users.html)

Allows administrators to manage account metadata and account status:

- Deactivate or reactivate users.
- Generate reset links.
- Delete users and their saved checks.

### Feedback: `/admin/feedback`

Template: [templates/admin_feedback.html](templates/admin_feedback.html)

Shows submitted usefulness feedback without exposing patient result details.

### Audit log: `/admin/audit`

Template: [templates/admin_audit.html](templates/admin_audit.html)

Shows security and administrative events with filtering support.

### System: `/admin/system`

Template: [templates/admin_system.html](templates/admin_system.html)

Shows service health, storage information, and available backups. It can
create a database backup.

### Admin export: `GET /admin/export.csv`

Exports aggregate administrative metrics as CSV. It does not export individual
patient assessments.

## 7. Runtime processing flow

The main request path is:

1. User submits the assessment to `POST /predict`.
2. [validation.py](validation.py) validates required fields, types, and bounds.
3. [rule_matrix.py](rule_matrix.py) computes transparent rule scores.
4. [clinical_model.py](clinical_model.py) and the model files compute calibrated
   estimates when available.
5. [recommendations.py](recommendations.py) creates guidance.
6. Patient-specific risk drivers are generated.
7. Optional lab interpretation is included.
8. The assessment is saved only when the user selects history saving.
9. The result page is rendered.
10. A short-lived print token is generated for the current result.

The active model files are:

- `model/cardiovascular_model.pkl`
- `model/general_burden_model.pkl`
- `model/neuropathy_mobility_model.pkl`
- `model/retinopathy_model.pkl`

The model summary and metadata are in
[model/training_summary.json](model/training_summary.json).

## 8. Data ownership and storage

Every history read or mutation is ownership-scoped:

- Signed-in users see records where `assessments.user_id` matches their user ID.
- Guests see records where the session ID matches and `user_id` is null.
- A record owned by another user or session returns not found.

The configured backend can vary by environment. The repository supports the
local database architecture described in [ARCHITECTURE.md](ARCHITECTURE.md);
the current environment may configure PostgreSQL through `.env`. Do not expose
credentials or copy secrets into documentation.

Retention, encryption, WAL behavior, migrations, and deletion rules are owned
by [database.py](database.py). Runtime database files and keys are deployment
artifacts and must not be committed.

## 9. Security and accessibility invariants

Future changes must preserve:

- CSRF protection on every state-changing form.
- Server-side validation in addition to browser validation.
- Strict ownership checks on assessment records.
- Safe local-only post-auth redirects.
- Role checks on all `/admin` routes.
- No plaintext passwords or raw reset tokens.
- Strict security headers and the repository CSP.
- Existing form field names, IDs, labels, and ARIA attributes.
- Minimum touch target and visible keyboard-focus behavior.
- Plain language suitable for patients and caregivers.

Do not change clinical thresholds, model weights, rule scores, or guideline
metrics during UI or documentation work.

## 10. Important implementation files

- [app.py](app.py): routes, sessions, authentication, model orchestration,
  request handling, headers, and result assembly.
- [database.py](database.py): persistence, ownership, migrations, retention,
  backups, and deletion.
- [validation.py](validation.py): input validation and bounds.
- [rule_matrix.py](rule_matrix.py): transparent clinical scoring.
- [clinical_model.py](clinical_model.py): model feature selection and risk
  labels.
- [recommendations.py](recommendations.py): recommendations and follow-up
  guidance.
- [templates/](templates/): Jinja2 page views.
- [static/js/](static/js/): assessment, history, results, print, and menu
  behavior.
- [static/css/](static/css/): compiled styling and clinical design system.
- [ARCHITECTURE.md](ARCHITECTURE.md): technical request flow and deployment.
- [README.md](README.md): setup commands, scope, and route overview.
- [PLAN_ACCOUNTS.md](PLAN_ACCOUNTS.md): account, history, and admin rules.

## 11. Local operation

Start the development site:

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

Production-style local serving uses:

```powershell
python wsgi.py
```

The readiness endpoint is:

```text
http://127.0.0.1:5000/health
```

Before changing runtime behavior, inspect the current implementation and run
the repository's applicable verification suites.
