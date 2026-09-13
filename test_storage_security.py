"""Isolated SQLCipher, migration, backup, and restore verification."""

import hashlib
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import sqlcipher3

import database


def _encrypted_fixture(path, key):
    conn = sqlcipher3.connect(path)
    conn.execute(f"PRAGMA key = '{key}'")
    conn.execute("CREATE TABLE assessments (id INTEGER PRIMARY KEY, marker TEXT)")
    conn.execute("INSERT INTO assessments (marker) VALUES ('encrypted fixture')")
    conn.commit()
    conn.close()


def test_wrong_key_and_standard_sqlite_rejected():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "encrypted.db")
        _encrypted_fixture(path, "correct-key")

        wrong = sqlcipher3.connect(path)
        wrong.execute("PRAGMA key = 'wrong-key'")
        try:
            try:
                wrong.execute("SELECT * FROM assessments").fetchall()
            except Exception:
                pass
            else:
                raise AssertionError("Wrong SQLCipher key was accepted")
        finally:
            wrong.close()

        plain = sqlite3.connect(path)
        try:
            try:
                plain.execute("SELECT * FROM assessments").fetchall()
            except Exception:
                pass
            else:
                raise AssertionError("Standard SQLite opened encrypted data")
        finally:
            plain.close()


def test_legacy_key_is_converted_to_dpapi():
    with tempfile.TemporaryDirectory() as directory:
        original_key_path = database.KEY_PATH
        original_protected_key_path = database.PROTECTED_KEY_PATH
        database.KEY_PATH = os.path.join(directory, ".db.key")
        database.PROTECTED_KEY_PATH = os.path.join(directory, ".db.key.dpapi")
        try:
            with open(database.KEY_PATH, "w", encoding="utf-8") as key_file:
                key_file.write("legacy-key")
            assert database._load_database_key() == "legacy-key"
            assert not os.path.exists(database.KEY_PATH)
            assert os.path.exists(database.PROTECTED_KEY_PATH)
            assert database._load_database_key() == "legacy-key"
        finally:
            database.KEY_PATH = original_key_path
            database.PROTECTED_KEY_PATH = original_protected_key_path


def test_interrupted_migration_preserves_plaintext_source():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "legacy.db")
        source = sqlite3.connect(path)
        source.execute("CREATE TABLE assessments (id INTEGER PRIMARY KEY, marker TEXT)")
        source.execute("INSERT INTO assessments (marker) VALUES ('legacy fixture')")
        source.commit()
        source.close()

        original_verify = database.verify_database_integrity
        database.verify_database_integrity = lambda conn=None: (_ for _ in ()).throw(RuntimeError("simulated interruption"))
        try:
            try:
                database.migrate_plaintext_database(path, "migration-key")
            except RuntimeError:
                pass
            else:
                raise AssertionError("Interrupted migration did not fail")
        finally:
            database.verify_database_integrity = original_verify

        legacy = sqlite3.connect(path)
        assert legacy.execute("SELECT marker FROM assessments").fetchone()[0] == "legacy fixture"
        legacy.close()
        assert not list(Path(directory).glob("*.sqlcipher-migration-*.tmp"))
        assert list(Path(directory).glob("legacy.db.plaintext-backup-*"))


def test_encrypted_backup_checksum_and_restore():
    with tempfile.TemporaryDirectory() as directory:
        original_db_path = database.DB_PATH
        original_key_path = database.KEY_PATH
        original_protected_key_path = database.PROTECTED_KEY_PATH
        database.DB_PATH = os.path.join(directory, "diabetes_system.db")
        database.KEY_PATH = os.path.join(directory, ".db.key")
        database.PROTECTED_KEY_PATH = os.path.join(directory, ".db.key.dpapi")
        try:
            _encrypted_fixture(database.DB_PATH, "backup-key")
            with open(database.KEY_PATH, "w", encoding="utf-8") as key_file:
                key_file.write("backup-key")

            bundle_path = os.path.join(directory, "backup.zip")
            database.create_backup_bundle(bundle_path)
            with zipfile.ZipFile(bundle_path) as bundle:
                db_bytes = bundle.read("diabetes_system.db")
                manifest = bundle.read("SHA256SUM").decode("ascii")
                assert hashlib.sha256(db_bytes).hexdigest() in manifest

            conn = database.get_connection()
            conn.execute("UPDATE assessments SET marker = 'changed'")
            conn.commit()
            conn.close()
            database.restore_backup_bundle(bundle_path)
            conn = database.get_connection()
            assert conn.execute("SELECT marker FROM assessments").fetchone()[0] == "encrypted fixture"
            conn.close()
        finally:
            database.DB_PATH = original_db_path
            database.KEY_PATH = original_key_path
            database.PROTECTED_KEY_PATH = original_protected_key_path


def test_invalid_restore_candidate_is_removed():
    with tempfile.TemporaryDirectory() as directory:
        original_db_path = database.DB_PATH
        original_key_path = database.KEY_PATH
        original_protected_key_path = database.PROTECTED_KEY_PATH
        database.DB_PATH = os.path.join(directory, "diabetes_system.db")
        database.KEY_PATH = os.path.join(directory, ".db.key")
        database.PROTECTED_KEY_PATH = os.path.join(directory, ".db.key.dpapi")
        try:
            _encrypted_fixture(database.DB_PATH, "restore-key")
            with open(database.KEY_PATH, "w", encoding="utf-8") as key_file:
                key_file.write("restore-key")

            invalid_db = os.path.join(directory, "invalid.db")
            _encrypted_fixture(invalid_db, "different-key")
            bundle_path = os.path.join(directory, "invalid-backup.zip")
            with zipfile.ZipFile(bundle_path, "w") as bundle:
                with open(invalid_db, "rb") as database_file:
                    database_bytes = database_file.read()
                bundle.writestr("diabetes_system.db", database_bytes)
                bundle.writestr(
                    "SHA256SUM",
                    f"{hashlib.sha256(database_bytes).hexdigest()}  diabetes_system.db\n",
                )

            try:
                database.restore_backup_bundle(bundle_path)
            except Exception:
                pass
            else:
                raise AssertionError("Restore accepted a database encrypted with another key")

            assert not list(Path(directory).glob("*.restore-*.tmp"))
            conn = database.get_connection()
            assert conn.execute("SELECT marker FROM assessments").fetchone()[0] == "encrypted fixture"
            conn.close()
        finally:
            database.DB_PATH = original_db_path
            database.KEY_PATH = original_key_path
            database.PROTECTED_KEY_PATH = original_protected_key_path


if __name__ == "__main__":
    test_wrong_key_and_standard_sqlite_rejected()
    test_legacy_key_is_converted_to_dpapi()
    test_interrupted_migration_preserves_plaintext_source()
    test_encrypted_backup_checksum_and_restore()
    test_invalid_restore_candidate_is_removed()
    print("[SQLCIPHER STORAGE SECURITY TESTS PASSED]")
