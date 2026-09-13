# Phase 1 Deployment Hardening and Pilot Runbook

This runbook is the release gate for a supervised local Windows pilot. It complements the automated tests; it does not replace clean-machine testing.

## Release invariants

- The packaged application must load `sqlcipher3` and report a non-empty SQLCipher version.
- The database must open only with SQLCipher and the installation key. Standard SQLite must fail to read it.
- Windows installations must store the database key in user-scoped DPAPI (`.db.key.dpapi`). Do not ship or create a plaintext `.db.key`.
- The server must listen only on `127.0.0.1`. A LAN device must not be able to connect to the application port.
- A missing or unusable key must fail closed. The application must not create a replacement database over an existing database.
- Support diagnostics must be collected through `/diagnostics/export`; never request the database, WAL/SHM files, key files, or raw patient exports.

## Clean Windows 10/11 test matrix

Run each case with the packaged executable, outside the source checkout, using a disposable test account where noted. Record OS build, package version, SQLCipher version, result, and evidence.

| Case | Procedure | Expected result |
|---|---|---|
| Fresh install | Install to a path without an existing database; start the app and open `/health`. | Health is 200; all four models load; encrypted database and `.db.key.dpapi` are created; `.db.key` is absent. |
| Native library packaging | Inspect the installed package and start the app without Python or the source checkout on `PATH`. | Startup succeeds and the bundled SQLCipher native library is used; diagnostics reports a SQLCipher version. |
| Same-user restart | Complete an assessment, stop the app, restart it as the same Windows user, and open history. | The original records remain readable and new records can be saved. |
| Different Windows user | Copy the installed database and DPAPI key file to a second user profile and start the app. | Key access fails closed; no replacement database is created; the original files remain unchanged. |
| Profile loss | Remove or make the original user profile unavailable while retaining the database. | Startup fails closed and requests recovery; it does not generate a new key or overwrite the database. |
| Replacement machine | Restore a backup on a new machine without the original DPAPI context. | The backup is rejected unless the separately protected recovery key is supplied through the approved recovery procedure. |
| Backup and restore | Download `/data/backup`, verify the ZIP manifest, alter a byte, and attempt restore; then restore the untouched bundle. | Altered bundle is rejected and the active database is unchanged; untouched bundle restores successfully. |
| Upgrade | Install the next package over a pilot installation containing assessments, then restart. | Records, schema migrations, key protection, and localhost binding remain intact. |
| Uninstall | Uninstall, then inspect the documented data-retention choice. | The installer behavior is documented and deliberate; patient data is not silently copied or uploaded. |
| Port conflict | Occupy the configured port and start the app. | Startup reports a clear bind failure; it does not switch to another interface or expose a remote listener. |
| Localhost exposure | Check `netstat -ano` or `Get-NetTCPConnection` while running; attempt access from another machine. | Listener is `127.0.0.1:<PORT>` only; remote access fails. |
| SmartScreen/AV | Test the signed release package with the organization's Windows Defender and antivirus policy. | Any warning is documented with the release hash and disposition; no security product is bypassed. |

## Windows package verification

The repository currently has no checked-in executable or installer. Build the PyInstaller `onedir` package on Windows with the pinned application dependencies and the spec file:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --clean --noconfirm packaging/windows/diabeates.spec
python packaging/windows/verify_sqlcipher_bundle.py
```

Run the verifier on the build host to confirm the expected native module before packaging. On the clean VM, launch `dist\DiaBeates\DiaBeates.exe` without Python or the source checkout on `PATH`, then confirm `/health` and `/diagnostics/export` report a SQLCipher version. For an existing encrypted database, set `DIABEATES_DB_KEY` from the approved secret vault for the duration of the test. Never put the key in a command line, script, installer property, or artifact.

## Recovery procedure

1. Stop the application and preserve the encrypted backup ZIP and its checksum manifest.
2. Record the package version, Windows build, SQLCipher version from diagnostics, and the exact error message. Do not collect raw database files.
3. On the replacement installation, install the same or a newer supported package and establish the approved protected key source. DPAPI-protected keys are user- and machine-context dependent; copying `.db.key.dpapi` alone is not a recovery method.
4. Restore the untouched encrypted bundle through the history page or the approved operator procedure. The application validates the ZIP contents, SHA-256 manifest, SQLCipher key, integrity, and required schema before replacement.
5. Confirm `/health`, record counts, representative history, print output, and a new assessment. Preserve the failed bundle and logs only if they contain no patient data.

If the key is lost, recovery is intentionally impossible. Do not use a raw database copy, plaintext export, guessed key, or standard SQLite tooling as a workaround. The pilot must establish a separately protected recovery-key escrow before handling real patient data.

### Replacement-machine drill

Before pilot enrollment, escrow the generated database key in an approved enterprise secret vault with dual-control access and an audit trail. The escrow record must identify the installation, database backup set, package version, and rotation date, but must not contain patient data.

To rehearse recovery, create an encrypted backup, provision a clean Windows VM, install the same package, inject the escrowed key only as the protected `DIABEATES_DB_KEY` process secret, and restore the backup through the application. Confirm `/health`, assessment counts, representative history, print output, and a new assessment. Remove the process secret after the drill and retain only the drill evidence.

DPAPI files are intentionally not portable recovery artifacts: copying `.db.key.dpapi` to another profile or machine must fail. A failed drill blocks patient rollout until the secret-vault procedure is corrected.

## Support diagnostics

Ask the operator to download `/diagnostics/export` from the local history page. The ZIP contains technical status and a filtered application log only. It must not contain assessment rows, patient fields, session identifiers, database paths, database files, WAL/SHM files, or key material. Review the archive before sending it to support.

## Automated pre-release checks

```powershell
python test_storage_security.py
python test_clinical_system.py
python -m compileall -q database.py app.py wsgi.py test_storage_security.py test_clinical_system.py
```

The automated suite cannot prove packaged native-library inclusion, DPAPI behavior under another profile, SmartScreen/antivirus disposition, uninstall semantics, or remote-network isolation. Those remain production blockers until the clean Windows matrix is executed and recorded.