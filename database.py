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

import sqlite3
import json
import os
import getpass
import platform
import subprocess
from datetime import datetime, timedelta, timezone

from rule_matrix import compute_lab_assessment

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diabetes_system.db")
SCHEMA_VERSION = 4


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def restrict_database_permissions():
    """Best-effort: restrict SQLite files to the current OS user (where supported)."""

    for path in (DB_PATH, f"{DB_PATH}-wal", f"{DB_PATH}-shm"):
        if not os.path.exists(path):

            continue



        if platform.system() == "Windows":

            subprocess.run(
                ["icacls", path, "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
                check=False,
                capture_output=True,
                text=True,
            )
        else:

            try:

                os.chmod(path, 0o600)

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
