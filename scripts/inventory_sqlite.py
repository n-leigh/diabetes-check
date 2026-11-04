"""Read-only inventory for the local SQLCipher database.

The script requires DIABEATES_DB_KEY in the process environment. It never
calls application initialization or writes to the database.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import sqlcipher3


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "diabetes_system.db"
KEY_ENVIRONMENT_VARIABLE = "DIABEATES_DB_KEY"


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> int:
    key = os.getenv(KEY_ENVIRONMENT_VARIABLE, "").strip()
    if not key:
        print(f"{KEY_ENVIRONMENT_VARIABLE} is not set; inventory not run.")
        return 2
    if not DB_PATH.exists():
        print("Database file is missing; inventory not run.")
        return 2

    connection = sqlcipher3.connect(str(DB_PATH), timeout=10.0)
    try:
        connection.execute(f"PRAGMA key = {sql_literal(key)}")
        connection.execute("PRAGMA query_only = ON")
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()

        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        print(f"database_path={DB_PATH}")
        print(f"schema_version={schema_version}")

        tables = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        print(f"table_count={len(tables)}")

        for table_name, create_sql in tables:
            quoted_table = '"' + table_name.replace('"', '""') + '"'
            columns = connection.execute(
                f"PRAGMA table_info({quoted_table})"
            ).fetchall()
            column_names = [column[1] for column in columns]
            row_count = connection.execute(
                f"SELECT count(*) FROM {quoted_table}"
            ).fetchone()[0]
            id_bounds = "UNKNOWN"
            if "id" in column_names:
                id_bounds = connection.execute(
                    f"SELECT min(id), max(id) FROM {quoted_table}"
                ).fetchone()
            timestamp_column = next(
                (name for name in ("created_at", "updated_at") if name in column_names),
                None,
            )
            timestamp_bounds = "UNKNOWN"
            if timestamp_column:
                quoted_timestamp = '"' + timestamp_column.replace('"', '""') + '"'
                timestamp_bounds = connection.execute(
                    f"SELECT min({quoted_timestamp}), max({quoted_timestamp}) "
                    f"FROM {quoted_table}"
                ).fetchone()

            print(f"\n[{table_name}]")
            print(f"rows={row_count}")
            print(f"id_min_max={id_bounds}")
            print(f"timestamp_min_max={timestamp_bounds}")
            print("columns:")
            for column in columns:
                print(
                    f"  {column[1]} type={column[2] or 'UNKNOWN'} "
                    f"not_null={bool(column[3])} default={column[4]!r} pk={column[5]}"
                )
                quoted_column = '"' + column[1].replace('"', '""') + '"'
                null_count = connection.execute(
                    f"SELECT count(*) FROM {quoted_table} "
                    f"WHERE {quoted_column} IS NULL"
                ).fetchone()[0]
                print(f"    null_count={null_count}")

            indexes = connection.execute(
                f"PRAGMA index_list({quoted_table})"
            ).fetchall()
            print("indexes:")
            for index in indexes:
                print(f"  {index[1]} unique={bool(index[2])}")
            print(f"create_sql_present={bool(create_sql)}")
    except Exception as error:
        print(f"Inventory failed without modifying the database: {error}", file=sys.stderr)
        return 1
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
