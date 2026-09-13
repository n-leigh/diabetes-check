"""Verify that a packaged runtime exposes SQLCipher, not standard SQLite."""

import argparse
import os
from pathlib import Path

import sqlcipher3


def verify_native_driver() -> str:
    connection = sqlcipher3.connect(":memory:")
    try:
        version = connection.execute("PRAGMA cipher_version").fetchone()[0]
    finally:
        connection.close()
    if not version:
        raise RuntimeError("SQLCipher PRAGMA cipher_version returned no version")

    package_dir = Path(sqlcipher3.__file__).resolve().parent
    native_modules = list(package_dir.glob("*_sqlite3*.pyd"))
    if not native_modules:
        raise RuntimeError(f"No SQLCipher native module found under {package_dir}")
    return str(version)


def verify_database(database_path: str) -> None:
    key = os.environ.get("DIABEATES_DB_KEY", "").strip()
    if not key:
        raise RuntimeError("Set DIABEATES_DB_KEY only from the approved protected secret source")
    connection = sqlcipher3.connect(database_path)
    try:
        escaped_key = key.replace("'", "''")
        connection.execute(f"PRAGMA key = '{escaped_key}'")
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        result = connection.execute("PRAGMA cipher_integrity_check").fetchone()[0]
        if str(result).lower() != "ok":
            raise RuntimeError(f"SQLCipher integrity check failed: {result}")
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", help="Existing encrypted database to verify")
    args = parser.parse_args()
    version = verify_native_driver()
    if args.database:
        verify_database(args.database)
    print(f"SQLCipher native verification passed: {version}")


if __name__ == "__main__":
    main()