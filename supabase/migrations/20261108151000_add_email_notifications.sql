-- Optional account email notifications. Run after the verification migration.
-- Take a backup before applying.

alter table public.users
    add column if not exists email_notifications boolean not null default false;

-- Rollback:
-- alter table public.users drop column if exists email_notifications;
