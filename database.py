"""
database.py — SQLite backend for DiaBeates.

Normalized into 4 tables rather than one flat table of JSON blobs:

  assessments      — one row per submission: the raw inputs, an anonymous
                      session_id (so each visitor's history stays private
                      to them), and which rule_matrix version scored it.
  risk_results      — one row per (assessment, category): rule score,
                      rule label, model prediction, AND model confidence
                      (the classifier's predicted probability — not just
                      the label, which is easy to add later but easy to
                      forget to capture at write time if you don't do it
                      from the start).
  lab_assessments   — one row per assessment IF lab values were given.
  feedback          — one row per "was this helpful?" click, so real
                      usage signal exists for any future model iteration,
                      not just the offline training metrics.

get_assessment()/get_all_assessments() reconstruct the same nested dict
shape the templates already expect, so upgrading the storage layer
doesn't require touching app.py's rendering logic.

SCHEMA_VERSION is tracked with SQLite's built-in PRAGMA user_version.
Migrations are additive and preserve existing assessment data.
"""

import hashlib
import json
import os
import ctypes
import getpass
import platform
import secrets
import sqlite3
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from ctypes import wintypes

import sqlcipher3

from rule_matrix import compute_lab_assessment

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diabetes_system.db")
KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".db.key")
PROTECTED_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".db.key.dpapi")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_VERSION = 4
_KEY_ENVIRONMENT_VARIABLE = "DIABEATES_DB_KEY"


def get_sqlcipher_version() -> str:
    conn = _open_cipher_connection(DB_PATH, _load_database_key())
    try:
        return str(conn.execute("PRAGMA cipher_version").fetchone()[0])
    finally:
        conn.close()


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if platform.system() == "Windows":
    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_protect(value: str) -> bytes:
    if platform.system() != "Windows":
        raise RuntimeError("Windows DPAPI is required for local database key storage")
    raw = value.encode("utf-8")
    raw_buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    input_blob = _DataBlob(len(raw), raw_buffer)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob), "DiaBeates database key", None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _dpapi_unprotect(protected: bytes) -> str:
    if platform.system() != "Windows":
        raise RuntimeError("Windows DPAPI is required for local database key storage")
    protected_buffer = (ctypes.c_ubyte * len(protected)).from_buffer_copy(protected)
    input_blob = _DataBlob(len(protected), protected_buffer)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _write_protected_key(key: str) -> None:
    protected = _dpapi_protect(key)
    temporary_path = f"{PROTECTED_KEY_PATH}.tmp-{secrets.token_hex(8)}"
    try:
        with open(temporary_path, "wb") as key_file:
            key_file.write(protected)
        restrict_database_permissions(temporary_path)
        os.replace(temporary_path, PROTECTED_KEY_PATH)
        restrict_database_permissions(PROTECTED_KEY_PATH)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def _load_database_key() -> str:
    key = os.getenv(_KEY_ENVIRONMENT_VARIABLE, "").strip()
    if key:
        return key
    if os.path.exists(PROTECTED_KEY_PATH):
        with open(PROTECTED_KEY_PATH, "rb") as key_file:
            key = _dpapi_unprotect(key_file.read()).strip()
        if key:
            return key
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, encoding="utf-8") as key_file:
            key = key_file.read().strip()
        if key:
            _write_protected_key(key)
            os.remove(KEY_PATH)
            return key
    if platform.system() != "Windows":
        raise RuntimeError("DIABEATES_DB_KEY is required outside Windows; refusing unprotected key storage")
    key = secrets.token_hex(32)
    _write_protected_key(key)
    return key


def _apply_key(conn, key: str) -> None:
    conn.execute(f"PRAGMA key = {_sql_literal(key)}")


def _open_cipher_connection(path: str, key: str):
    conn = sqlcipher3.connect(path, timeout=10.0)
    _apply_key(conn, key)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _database_is_readable(path: str, key: str) -> bool:
    conn = None
    try:
        conn = _open_cipher_connection(path, key)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return True
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def _database_is_plaintext(path: str) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(path, timeout=10.0)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return True
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def _copy_legacy_database(path: str) -> str:
    backup_path = f"{path}.plaintext-backup-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(path, backup_path)
    for suffix in ("-wal", "-shm"):
        sidecar = f"{path}{suffix}"
        if os.path.exists(sidecar):
            shutil.copy2(sidecar, f"{backup_path}{suffix}")
    restrict_database_permissions(backup_path)
    return backup_path


def migrate_plaintext_database(path: str = None, key: str = None) -> bool:
    """Convert a legacy SQLite file to SQLCipher without replacing its source early."""
    path = path or DB_PATH
    key = key or _load_database_key()
    if not os.path.exists(path) or _database_is_readable(path, key):
        return False
    if not _database_is_plaintext(path):
        raise RuntimeError(f"Database is neither valid SQLCipher nor readable legacy SQLite: {path}")

    legacy_backup = _copy_legacy_database(path)
    temporary_path = f"{path}.sqlcipher-migration-{secrets.token_hex(8)}.tmp"
    try:
        source = sqlite3.connect(path, timeout=10.0)
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        source_schema_version = source.execute("PRAGMA user_version").fetchone()[0]
        destination = _open_cipher_connection(temporary_path, key)
        try:
            destination.executescript("\n".join(source.iterdump()))
            destination.commit()
        finally:
            destination.close()
            source.close()

        encrypted = _open_cipher_connection(temporary_path, key)
        try:
            encrypted.execute(f"PRAGMA user_version = {int(source_schema_version)}")
            encrypted.commit()
            verify_database_integrity(encrypted)
        finally:
            encrypted.close()
        os.replace(temporary_path, path)
        restrict_database_permissions(path)
        return True
    except Exception:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        raise RuntimeError(
            f"SQLCipher migration failed; original database preserved at {legacy_backup}"
        ) from None


def verify_database_integrity(conn=None) -> bool:
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
        if str(result).lower() != "ok":
            raise RuntimeError(f"Database integrity check failed: {result}")
        return True
    finally:
        if owns_connection:
            conn.close()


def _encrypted_database_copy() -> str:
    temporary_path = f"{DB_PATH}.backup-{secrets.token_hex(8)}.tmp"
    source = get_connection()
    destination = _open_cipher_connection(temporary_path, _load_database_key())
    source.backup(destination)
    destination.close()
    source.close()
    copy_connection = _open_cipher_connection(temporary_path, _load_database_key())
    try:
        verify_database_integrity(copy_connection)
    finally:
        copy_connection.close()
    return temporary_path


def create_backup_bundle(output_path: str = None) -> str:
    """Create a self-verifying ZIP containing only an encrypted database."""
    if output_path is None:
        backup_directory = os.path.join(BASE_DIR, "backups")
        os.makedirs(backup_directory, exist_ok=True)
        output_path = os.path.join(
            backup_directory,
            f"diabeates-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip",
        )
    encrypted_copy = _encrypted_database_copy()
    try:
        with open(encrypted_copy, "rb") as db_file:
            digest = hashlib.sha256(db_file.read()).hexdigest()
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(encrypted_copy, arcname="diabetes_system.db")
            bundle.writestr("SHA256SUM", f"{digest}  diabetes_system.db\n")
        restrict_database_permissions(output_path)
        return output_path
    finally:
        if os.path.exists(encrypted_copy):
            os.remove(encrypted_copy)


def restore_backup_bundle(bundle_path: str) -> None:
    """Validate and atomically restore an encrypted backup bundle."""
    with zipfile.ZipFile(bundle_path, "r") as bundle:
        names = set(bundle.namelist())
        if names != {"diabetes_system.db", "SHA256SUM"}:
            raise ValueError("Backup bundle contains unexpected files")
        database_bytes = bundle.read("diabetes_system.db")
        manifest = bundle.read("SHA256SUM").decode("ascii").strip().split()
        if len(manifest) != 2 or manifest[1] != "diabetes_system.db":
            raise ValueError("Backup checksum manifest is invalid")
        if hashlib.sha256(database_bytes).hexdigest() != manifest[0]:
            raise ValueError("Backup checksum verification failed")

    temporary_path = f"{DB_PATH}.restore-{secrets.token_hex(8)}.tmp"
    with open(temporary_path, "wb") as database_file:
        database_file.write(database_bytes)
    restrict_database_permissions(temporary_path)
    candidate = None
    try:
        candidate = _open_cipher_connection(temporary_path, _load_database_key())
        verify_database_integrity(candidate)
        if candidate.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'assessments'").fetchone() is None:
            raise ValueError("Backup database is missing the assessments table")
        candidate.close()
        candidate = None
        os.replace(temporary_path, DB_PATH)
        restrict_database_permissions(DB_PATH)
    finally:
        if candidate is not None:
            candidate.close()
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def get_connection():
    if not os.path.exists(DB_PATH):
        _load_database_key()
    migrate_plaintext_database(DB_PATH)
    conn = _open_cipher_connection(DB_PATH, _load_database_key())
    conn.row_factory = sqlcipher3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def restrict_database_permissions(path: str = None):
    """Best-effort: restrict SQLite files to the current OS user (where supported)."""

    paths = (path,) if path else (DB_PATH, f"{DB_PATH}-wal", f"{DB_PATH}-shm", KEY_PATH)
    for current_path in paths:
        if not os.path.exists(current_path):

            continue



        if platform.system() == "Windows":

            subprocess.run(
                ["icacls", current_path, "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
                check=False,
                capture_output=True,
                text=True,
            )
        else:

            try:

                os.chmod(current_path, 0o600)

            except OSError:

                pass



def init_db():
    conn = get_connection()
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version > SCHEMA_VERSION:
        conn.close()
        raise RuntimeError(
            f"Database schema version {current_version} is newer than supported version {SCHEMA_VERSION}"
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            rule_matrix_version TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            bmi REAL, age_band INTEGER, gen_hlth INTEGER, sex INTEGER,
            phys_hlth INTEGER, ment_hlth INTEGER,
            high_bp INTEGER, high_chol INTEGER, smoker INTEGER,
            heart_disease INTEGER, stroke INTEGER, diff_walk INTEGER,
            no_doc_cost INTEGER, diabetes_duration INTEGER, blurry_vision INTEGER
        )
    """)

    # Safe schema migration for existing sqlite database
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(assessments)").fetchall()]
    if "diabetes_duration" not in existing_cols:
        conn.execute("ALTER TABLE assessments ADD COLUMN diabetes_duration INTEGER DEFAULT 0")
    if "blurry_vision" not in existing_cols:
        conn.execute("ALTER TABLE assessments ADD COLUMN blurry_vision INTEGER DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS risk_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL REFERENCES assessments(id),
            category TEXT NOT NULL,
            rule_score INTEGER, rule_percentage INTEGER, rule_label TEXT,
            model_name TEXT, model_label TEXT, model_confidence REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lab_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL REFERENCES assessments(id),
            hba1c REAL, systolic_bp INTEGER, ldl INTEGER,
            label TEXT, percentage INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL REFERENCES assessments(id),
            created_at TEXT NOT NULL,
            helpful INTEGER NOT NULL,
            comment TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assessments_session_archived_id ON assessments(session_id, archived, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assessments_created_at ON assessments(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_risk_results_assessment_id ON risk_results(assessment_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lab_assessments_assessment_id ON lab_assessments(assessment_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_assessment_id ON feedback(assessment_id)")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    conn.close()
    restrict_database_permissions()


def save_assessment(session_id: str, patient: dict, rule_results: dict,
                     model_results: dict, lab_assessment: dict = None,
                     model_confidences: dict = None, model_names: dict = None,
                     rule_version: str = "1.0") -> int:
    model_confidences = model_confidences or {}
    model_names = model_names or {}
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO assessments
           (session_id, created_at, rule_matrix_version, bmi, age_band, gen_hlth, sex,
            phys_hlth, ment_hlth, high_bp, high_chol, smoker, heart_disease, stroke,
            diff_walk, no_doc_cost, diabetes_duration, blurry_vision)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                rule_version,
                patient.get("BMI"), patient.get("Age"), patient.get("GenHlth"), patient.get("Sex"),
                patient.get("PhysHlth"), patient.get("MentHlth"),
                patient.get("HighBP", 0), patient.get("HighChol", 0), patient.get("Smoker", 0),
                patient.get("HeartDiseaseorAttack", 0), patient.get("Stroke", 0),
                patient.get("DiffWalk", 0), patient.get("NoDocbcCost", 0),
                patient.get("DiabetesDuration", 0), patient.get("BlurryVision", 0),
            ),
        )
        assessment_id = cur.lastrowid

        for category, result in rule_results.items():
            conf = model_confidences.get(category)
            conn.execute(
                """INSERT INTO risk_results
               (assessment_id, category, rule_score, rule_percentage, rule_label,
                model_name, model_label, model_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (assessment_id, category, result["score"], result["percentage"], result["label"],
                 model_names.get(category), model_results.get(category), conf),
            )

        if lab_assessment:
            d = lab_assessment.get("details", {})
            conn.execute(
                """INSERT INTO lab_assessments (assessment_id, hba1c, systolic_bp, ldl, label, percentage)
               VALUES (?, ?, ?, ?, ?, ?)""",
                (assessment_id,
                 d.get("hba1c", {}).get("value"), d.get("systolic_bp", {}).get("value"), d.get("ldl", {}).get("value"),
                 lab_assessment["label"], lab_assessment["percentage"]),
            )

        conn.commit()
        return assessment_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_feedback(assessment_id: int, helpful: bool, comment: str = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO feedback (assessment_id, created_at, helpful, comment) VALUES (?, ?, ?, ?)",
        (assessment_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), int(helpful), comment),
    )
    conn.commit()
    conn.close()


def _reconstruct(conn, row) -> dict:
    assessment_id = row["id"]

    patient = {
        "BMI": row["bmi"], "Age": row["age_band"], "GenHlth": row["gen_hlth"], "Sex": row["sex"],
        "PhysHlth": row["phys_hlth"], "MentHlth": row["ment_hlth"],
        "HighBP": row["high_bp"], "HighChol": row["high_chol"], "Smoker": row["smoker"],
        "HeartDiseaseorAttack": row["heart_disease"], "Stroke": row["stroke"],
        "DiffWalk": row["diff_walk"], "NoDocbcCost": row["no_doc_cost"],
        "DiabetesDuration": row["diabetes_duration"] if "diabetes_duration" in row.keys() else 0,
        "BlurryVision": row["blurry_vision"] if "blurry_vision" in row.keys() else 0,
    }

    rule_results = {}
    model_results = {}
    model_confidences = {}
    model_names = {}
    for r in conn.execute("SELECT * FROM risk_results WHERE assessment_id = ?", (assessment_id,)):
        rule_results[r["category"]] = {
            "score": r["rule_score"], "percentage": r["rule_percentage"], "label": r["rule_label"],
        }
        model_results[r["category"]] = r["model_label"]
        model_confidences[r["category"]] = r["model_confidence"]
        model_names[r["category"]] = r["model_name"]

    lab_row = conn.execute("SELECT * FROM lab_assessments WHERE assessment_id = ?", (assessment_id,)).fetchone()
    lab_assessment = None
    if lab_row:
        details = {}
        if lab_row["hba1c"] is not None:
            details["hba1c"] = {"value": lab_row["hba1c"]}
        if lab_row["systolic_bp"] is not None:
            details["systolic_bp"] = {"value": lab_row["systolic_bp"]}
        if lab_row["ldl"] is not None:
            details["ldl"] = {"value": lab_row["ldl"]}
        # Older rows store the values but not the per-measure points used by
        # the result template to select the correct guideline legend.
        recalculated = compute_lab_assessment(
            hba1c=details.get("hba1c", {}).get("value"),
            systolic_bp=details.get("systolic_bp", {}).get("value"),
            ldl=details.get("ldl", {}).get("value"),
        )
        if recalculated:
            for name, assessment in recalculated["details"].items():
                details[name]["points"] = assessment["points"]
        lab_assessment = {"label": lab_row["label"], "percentage": lab_row["percentage"], "details": details}

    return {
        "id": assessment_id,
        "session_id": row["session_id"],
        "created_at": row["created_at"],
        "rule_matrix_version": row["rule_matrix_version"],
        "archived": bool(row["archived"]),
        "patient": patient,
        "rule_results": rule_results,
        "model_results": model_results,
        "model_confidences": model_confidences,
        "model_names": model_names,
        "lab_assessment": lab_assessment,
    }


def get_all_assessments(session_id: str, limit: int = 200, archived: bool = False, sort_order: str = "desc"):
    """archived=False (default) returns active records; archived=True
    returns only archived ones. The two views are always mutually
    exclusive so nothing is silently duplicated or hidden between them.
    sort_order can be 'asc' (oldest first) or 'desc' (newest first)."""
    conn = get_connection()
    direction = "ASC" if str(sort_order).strip().lower() == "asc" else "DESC"
    rows = conn.execute(
        f"SELECT * FROM assessments WHERE session_id = ? AND archived = ? ORDER BY id {direction} LIMIT ?",
        (session_id, int(archived), limit),
    ).fetchall()
    result = [_reconstruct(conn, r) for r in rows]
    conn.close()
    return result


def get_assessment(assessment_id: int, session_id: str = None):
    """If session_id is given, only returns the record when it belongs to
    that session — callers use this to prevent one visitor from viewing
    or printing another visitor's assessment by guessing/incrementing IDs."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
    if not row:
        conn.close()
        return None
    if session_id is not None and row["session_id"] != session_id:
        conn.close()
        return None
    result = _reconstruct(conn, row)
    conn.close()
    return result


def set_archived(assessment_id: int, session_id: str, archived: bool) -> bool:
    """Returns True if a record belonging to this session was updated."""
    conn = get_connection()
    row = conn.execute("SELECT session_id FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
    if not row or row["session_id"] != session_id:
        conn.close()
        return False
    conn.execute("UPDATE assessments SET archived = ? WHERE id = ?", (int(archived), assessment_id))
    conn.commit()
    conn.close()
    return True


def delete_assessment(assessment_id: int, session_id: str) -> bool:
    """Permanently deletes an assessment and everything referencing it.
    Returns True if a record belonging to this session was deleted."""
    conn = get_connection()
    row = conn.execute("SELECT session_id FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
    if not row or row["session_id"] != session_id:
        conn.close()
        return False
    conn.execute("DELETE FROM feedback WHERE assessment_id = ?", (assessment_id,))
    conn.execute("DELETE FROM lab_assessments WHERE assessment_id = ?", (assessment_id,))
    conn.execute("DELETE FROM risk_results WHERE assessment_id = ?", (assessment_id,))
    conn.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))
    conn.commit()
    conn.close()
    return True


def prune_expired_assessments(days: int = 90) -> int:
    """Permanently deletes assessments older than `days` days and their child records.
    Returns the count of deleted assessment records to comply with GDPR storage limitation
    and HIPAA minimal retention policies."""
    if days < 1:
        raise ValueError("Retention period must be at least one day")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM assessments WHERE created_at < ?",
        (cutoff,)
    ).fetchall()
    if not rows:
        conn.close()
        return 0
    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" for _ in ids)
    conn.execute(f"DELETE FROM feedback WHERE assessment_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM lab_assessments WHERE assessment_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM risk_results WHERE assessment_id IN ({placeholders})", ids)
    cur = conn.execute(f"DELETE FROM assessments WHERE id IN ({placeholders})", ids)
    deleted_count = cur.rowcount
    conn.commit()
    conn.close()
    return deleted_count


def get_session_export_data(session_id: str) -> list:
    """Exports all assessments and child records for the given session_id."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM assessments WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        export_records = []
        for r in rows:
            rec = _reconstruct(conn, r)
            fb_rows = conn.execute(
                "SELECT helpful, comment, created_at FROM feedback WHERE assessment_id = ? ORDER BY id ASC",
                (r["id"],)
            ).fetchall()
            rec["feedback"] = [
                {"helpful": bool(fb["helpful"]), "comment": fb["comment"], "created_at": fb["created_at"]}
                for fb in fb_rows
            ]
            export_records.append(rec)
        return export_records
    finally:
        conn.close()


def clear_session_assessments(session_id: str) -> int:
    """Permanently deletes all assessments, feedback, lab assessments, and risk results
    belonging to session_id. Returns count of deleted assessments."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id FROM assessments WHERE session_id = ?",
            (session_id,)
        ).fetchall()
        if not rows:
            return 0
        ids = [r["id"] for r in rows]
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM feedback WHERE assessment_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM lab_assessments WHERE assessment_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM risk_results WHERE assessment_id IN ({placeholders})", ids)
        cur = conn.execute(f"DELETE FROM assessments WHERE id IN ({placeholders})", ids)
        deleted_count = cur.rowcount
        conn.commit()
        return deleted_count
    finally:
        conn.close()

