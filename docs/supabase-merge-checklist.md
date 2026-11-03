# DiaBeates Supabase Merge Checklist

This checklist is for the repository state after the initial schema migration.
It does not connect to hosted Supabase automatically and does not contain
secrets.

## Quick path

Follow these steps in order:

1. Install Git, Docker Desktop, Node.js, and the Supabase CLI.
2. Create branch `feature/supabase-migration`.
3. Start local Supabase with `npx supabase start`.
4. Apply the migrations locally with `npx supabase db reset`.
5. Verify the seven tables, RLS, and revoked Data API privileges.
6. Keep `DB_BACKEND=sqlite` until final validation.
7. Do not migrate real data or touch hosted Supabase until local checks pass.

**Current status:** the schema migrations, documentation, and Flask Postgres
adapter are implemented. Synthetic Supabase connectivity and a Flask
assessment flow have passed. Full local-stack parity tests remain.

## What is already prepared

- Local Supabase configuration: [`supabase/config.toml`](../supabase/config.toml)
- Initial schema migration:
  [`supabase/migrations/20261104004500_create_diabeates_schema.sql`](../supabase/migrations/20261104004500_create_diabeates_schema.sql)
- Password reset table migration:
  [`supabase/migrations/20261104011000_create_password_reset_tokens.sql`](../supabase/migrations/20261104011000_create_password_reset_tokens.sql)
- Non-secret environment names: [`.env.example`](../.env.example)
- Sensitive migration-path ignores: [`.gitignore`](../.gitignore)
- SQLite remains the configured default application backend.
- Flask supports a pooled Postgres backend with `DB_BACKEND=postgres`.
- Clinical files remain unchanged.

The adapter uses the server-side `SUPABASE_DB_URL` and never exposes Supabase
credentials to the browser.

## 1. Install and verify local tools

Install Git, Docker Desktop, Node.js, and the Supabase CLI. If the CLI is not
installed globally, use `npx supabase`.

```powershell
git --version
docker --version
node --version
npx supabase --version
docker info
```

Docker must be running before local Supabase commands are used.

## 2. Create and review the branch

```powershell
git checkout -b feature/supabase-migration
git status --short
```

Review the diff. Confirm that no `.env`, key, database, dump, export, or
patient data is staged.

## 3. Configure local variables

Copy the example file for local use:

```powershell
Copy-Item .env.example .env
```

Set only local values in `.env`. Keep:

```env
DB_BACKEND=sqlite
```

Do not commit `.env`.

## 4. Start the local Supabase stack

```powershell
npx supabase start
npx supabase status
```

Do not run `supabase link`, `supabase db push`, or any hosted command during
local validation.

## 5. Apply the migration locally

The following command recreates the local database. Use it only for the local
Supabase stack, never a hosted project:

```powershell
npx supabase db reset
```

If local data must be preserved, stop and use a separate disposable project
directory instead of resetting an existing database.

## 6. Verify the local schema

Use the local database connection shown by `npx supabase status`, or open the
local Studio URL and inspect SQL Editor.

Verify these tables exist:

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;
```

Expected application tables:

- `assessments`
- `audit_log`
- `feedback`
- `lab_assessments`
- `risk_results`
- `users`
- `password_reset_tokens`

`password_reset_tokens` is empty after migration. Existing reset tokens must be
invalidated during a future cutover; new tokens may be created by Flask after
the second migration is applied.

Verify RLS:

```sql
select schemaname, tablename, rowsecurity
from pg_tables
where schemaname = 'public'
order by tablename;
```

Every application table must report `rowsecurity = true`.

Verify privileges:

```sql
select grantee, table_name, privilege_type
from information_schema.role_table_grants
where table_schema = 'public'
  and grantee in ('anon', 'authenticated')
order by grantee, table_name, privilege_type;
```

This query must return no rows for the application tables.

## 7. Validate constraints and indexes

```sql
select
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type
from information_schema.table_constraints tc
where tc.table_schema = 'public'
order by tc.table_name, tc.constraint_name;
```

Check specifically:

- `users.email` is unique.
- `users.role` accepts only `user` and `admin`.
- `risk_results.category` accepts only the four clinical categories.
- `risk_results(assessment_id, category)` is unique.
- `lab_assessments.assessment_id` is unique.
- Child tables reference `assessments`.
- `assessments.user_id` references `users`.

## 8. Create the server-side database role

Do this only in the environment where Flask will run. Do not use the
`anon` or `authenticated` roles for Flask.

Create a dedicated least-privilege role according to your deployment policy.
The exact role name, password, network rules, and grants are deployment
decisions and must not be committed to this repository.

The role must be able to perform the repository operations required by Flask:

- read and write `users`;
- read, insert, update, and delete owned `assessments`;
- read and write related `risk_results`, `lab_assessments`, and `feedback`;
- insert and read permitted `audit_log` rows;
- use the identity sequences.

Because ownership remains enforced in Python, this role is trusted only by the
server. Never expose its connection string to browser JavaScript.

## 9. Approve and add the Postgres driver

This repository currently has no Postgres driver. Before implementation,
approve adding:

```text
psycopg[binary]
psycopg_pool
```

After approval, the implementation must add a pooled Postgres repository behind
`DB_BACKEND=postgres`, while preserving SQLite as the default. Waitress is
multi-threaded, so the pool must have bounded size and connection timeouts.

Do not change:

- [`rule_matrix.py`](../rule_matrix.py)
- [`clinical_model.py`](../clinical_model.py)
- [`validation.py`](../validation.py)
- [`recommendations.py`](../recommendations.py)

## 10. Run application tests with SQLite

Before switching any backend:

```powershell
python test_clinical_system.py
python test_both_flows.py
python live_browser_test.py
python -m pytest tests -q
```

The pytest command requires the test dependency to be installed. If it is not
available, install dependencies only after approval.

## 11. Load synthetic data locally

Use synthetic records only while validating the migration. Never use the real
database as a writable test source.

Import order:

1. `users`
2. `assessments`
3. `risk_results`
4. `lab_assessments`
5. `feedback`
6. `audit_log`

Do not import `password_reset_tokens`.

After importing explicit IDs, reset each identity sequence to the maximum
imported ID before allowing inserts.

## 12. Validate data integrity

Compare source and destination for:

- total row counts;
- per-assessment child counts;
- minimum and maximum IDs;
- UTC timestamp values;
- null counts;
- per-column checksums;
- BMI and lab values;
- recent, archived, guest, claimed, with-lab, and without-lab samples.

Confirm that deleting an assessment removes or handles children exactly as the
application expects.

## 13. Validate security behavior

Using local Supabase SQL sessions for `anon` and `authenticated`, verify that
selecting from every application table returns no rows and that inserts,
updates, and deletes are denied.

Then test Flask using the dedicated server-side role:

- guest session can access only its own records;
- authenticated local account can access only its own records;
- archive and delete remain ownership-scoped;
- admin routes retain application-level authorization;
- no database credentials appear in HTML, JavaScript, or logs.

## 14. Configure the application only after adapter completion

SQLite:

```env
DB_BACKEND=sqlite
```

Postgres:

```env
DB_BACKEND=postgres
SUPABASE_DB_URL=<server-side-secret>
```

Use a direct connection for administrative migrations when required. Use a
pooler connection for application traffic when appropriate. For IPv4-only
networks, confirm that the selected Supabase endpoint supports IPv4; do not
assume the direct endpoint and pooler endpoint have identical network support.

## 15. Retention scheduling

The current SQLite startup pruning cannot be assumed to run against Postgres.
Choose one approved mechanism:

- a protected scheduled Flask/Windows task;
- a scheduled CI job;
- `pg_cron`, if enabled and approved by the hosted plan.

Test that the job removes only records older than the configured retention
period and records failures without logging health data.

## 16. Hosted project checklist

Only after local validation:

1. Confirm project region and privacy approval.
2. Confirm the plan supports the required backups, retention, and scheduling.
3. Create a protected database backup.
4. Store connection secrets in the deployment secret manager.
5. Link the repository only with an approved operator account.
6. Review the migration SQL one more time.
7. Apply the migration to the intended project.
8. Verify tables, RLS, and privileges.
9. Perform the one-shot import during the approved write freeze.
10. Compare validation reports.
11. Keep SQLite read-only for rollback.

Never run `supabase db reset` against a hosted project.

## 17. GitHub merge checklist

```powershell
git add .env.example .gitignore supabase docs
git diff --cached --check
git diff --cached --name-only
git commit -m "Add Supabase schema foundation"
git push -u origin feature/supabase-migration
```

Open a pull request and require review for:

- schema and type choices;
- RLS and privilege revocation;
- data migration and rollback;
- secret scanning;
- clinical regression tests;
- dependency approval for the Postgres adapter.

Do not merge until the local migration has been applied and validated.

## 18. Rollback

Before application cutover:

1. Stop Postgres writes.
2. Keep `DB_BACKEND=sqlite`.
3. Restore the last verified SQLite backup if necessary.
4. Preserve migration logs without collecting patient data.

After application cutover:

1. Stop the Flask deployment.
2. Revert `DB_BACKEND=sqlite`.
3. Restore the last verified SQLite source.
4. Preserve Supabase validation evidence.
5. Reconcile any records created after cutover before resuming service.
