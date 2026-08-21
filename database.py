"""
database.py — SQLite persistence for patient assessments.

Every time someone submits the assessment form, we save their inputs +
the rule-matrix scores + the model predictions + any optional lab-based
assessment. This gives you an actual records/history feature to demo.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diabetes_system.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            patient_inputs TEXT NOT NULL,
            rule_results TEXT NOT NULL,
            model_results TEXT NOT NULL,
            lab_assessment TEXT
        )
    """)
    # migration safety net: if an older DB file already exists without
    # this column, add it rather than crashing on the next insert
    try:
        conn.execute("ALTER TABLE assessments ADD COLUMN lab_assessment TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


def save_assessment(patient: dict, rule_results: dict, model_results: dict, lab_assessment: dict = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO assessments (created_at, patient_inputs, rule_results, model_results, lab_assessment) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            json.dumps(patient),
            json.dumps(rule_results),
            json.dumps(model_results),
            json.dumps(lab_assessment) if lab_assessment else None,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def _row_to_dict(r):
    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "patient": json.loads(r["patient_inputs"]),
        "rule_results": json.loads(r["rule_results"]),
        "model_results": json.loads(r["model_results"]),
        "lab_assessment": json.loads(r["lab_assessment"]) if r["lab_assessment"] else None,
    }


def get_all_assessments(limit: int = 200):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM assessments ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_assessment(assessment_id: int):
    conn = get_connection()
    r = conn.execute(
        "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
    ).fetchone()
    conn.close()
    if not r:
        return None
    return _row_to_dict(r)
