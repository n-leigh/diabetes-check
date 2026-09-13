# SQLCipher Migration Plan

## Objective

Move `diabetes_system.db` from plaintext SQLite to SQLCipher-backed SQLite without losing assessments, changing the existing application data contract, or breaking additive schema migrations.

The runtime implementation now uses `sqlcipher3`, migrates legacy plaintext files on startup, verifies `PRAGMA quick_check`, and provides encrypted checksum-verified backup/restore. Windows key storage uses user-scoped DPAPI in `.db.key.dpapi`; managed deployments may provide `DIABEATES_DB_KEY` through a protected secret source.

## Compatibility contract

Keep these application-level contracts unchanged:

- `database.get_connection()` remains the only connection factory.
- `database.init_db()` remains responsible for schema creation and additive migrations.
- `PRAGMA user_version` remains the schema version for application migrations.
- Existing tables, columns, foreign keys, indexes, and reconstructed record dictionaries remain compatible.
- A database opened by an older application must be migrated before normal reads or writes.
- A database from a newer application must fail closed rather than be downgraded.

SQLCipher encryption is a storage-format migration, not an application schema migration. Track it separately from `SCHEMA_VERSION` with a format marker or encrypted-database metadata check.

## Transition sequence

### 1. Select and pin the encrypted driver

The selected driver is `sqlcipher3`, pinned by the project dependency range and verified in this environment as SQLCipher 4.12.0. Do not silently fall back to the standard `sqlite3` module when encryption is required.

Add a startup health check that verifies:

- The configured driver is SQLCipher-capable.
- The database key can be applied.
- `PRAGMA cipher_integrity_check` succeeds.
- The expected application schema version is supported.

### 2. Define key management before migration

Do not hard-code the key, store it beside the database in plaintext, or derive it from a predictable patient field. The installer creates a per-installation key and stores it with user-scoped Windows DPAPI in `.db.key.dpapi`; managed deployments may use a protected `DIABEATES_DB_KEY` secret.

Document recovery behavior before rollout. If the key is lost, the database cannot be recovered; provide an explicit encrypted export/backup flow rather than an undocumented support workaround.

### 3. Detect the existing format

At startup, classify the database path as:

1. Missing: create a new encrypted database.
2. Encrypted and valid: open with SQLCipher and continue.
3. Plaintext legacy SQLite: enter one-time migration mode.
4. Invalid, corrupt, or unknown: stop and preserve the original file.

Detection must not rely only on a filename. Use a read-only probe and confirm the expected tables/schema before migration.

### 4. Migrate plaintext to encrypted storage

Use a transactionally controlled conversion process:

1. Close application connections and create a byte-for-byte backup of the plaintext database, including `-wal` and `-shm` handling.
2. Open the legacy database with standard SQLite in read-only mode.
3. Create a new temporary SQLCipher database in the same directory with restrictive permissions.
4. Apply the key and copy schema/data using a structured backup/export operation, preserving `PRAGMA user_version`, foreign keys, indexes, timestamps, and row IDs.
5. Run row-count checks, foreign-key checks, and application-level record comparisons.
6. Run `PRAGMA cipher_integrity_check` on the encrypted copy.
7. Flush and close both databases.
8. Atomically rename the original to a clearly marked legacy backup and promote the encrypted file to `diabetes_system.db`.
9. Reopen through `get_connection()` and run `init_db()` so existing additive migrations continue normally.

Never delete the legacy source until the encrypted database has passed validation and a user-visible backup has been created.

### 5. Preserve rollback and recovery

Keep a versioned, encrypted backup and the original legacy backup for a bounded recovery period. If validation fails, leave the original database active and report a non-destructive migration error. Do not overwrite a valid database with a partially converted file.

Updates must support interruption between every rename step. On the next launch, detect temporary, legacy, and encrypted candidates and select only a validated complete database.

## Migration validation gates

Before pilot distribution, test:

- Empty install creates an encrypted database.
- Representative plaintext databases for every current schema version migrate successfully.
- Existing assessment counts and category rows are identical before and after migration.
- Historical results, print output, archive state, feedback, and lab values remain readable.
- WAL mode, backups, restore, retention pruning, and migrations work with the encrypted driver.
- Wrong keys and corrupted files fail closed without overwriting the source.
- Power loss simulation during conversion leaves a recoverable source database.
- The packaged Windows executable includes the correct SQLCipher native library.
- A raw file copy cannot be opened as ordinary SQLite and does not expose patient rows.

## Release and rollback

Release the encrypted storage behind a migration feature flag during internal testing only. The production gate is all-or-nothing: the application must not write new plaintext records after the encrypted release is enabled.

On rollback, use an explicit export/import recovery tool rather than pointing the old plaintext build at the encrypted file. Never downgrade by copying an encrypted database over a legacy installation without a tested conversion path.

## Operational tripwires

- Any migration that changes row counts: abort.
- Any failed cipher integrity check: abort.
- Any database opened by the standard SQLite driver after encryption rollout: release blocker.
- Any missing key or failed key-store access: read-only recovery screen, no replacement database.
- Any backup that cannot be restored in test: block patient rollout.
- Any support request for a raw patient database: require the encrypted diagnostic/export workflow instead.