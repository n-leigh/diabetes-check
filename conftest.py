import os
import tempfile


if os.getenv("DB_BACKEND", "").strip().lower() == "postgres" or os.getenv("SUPABASE_DB_URL", "").strip():
    raise RuntimeError("Tests refuse to run with hosted Postgres or Supabase configuration.")

_test_dir = tempfile.mkdtemp(prefix="diabeates-tests-")
os.environ["DB_BACKEND"] = "sqlite"
os.environ.pop("SUPABASE_DB_URL", None)
os.environ["DIABEATES_TEST_DB_PATH"] = os.path.join(_test_dir, "diabetes_system.db")
os.environ["DIABEATES_TEST_KEY_PATH"] = os.path.join(_test_dir, ".db.key")
os.environ["DIABEATES_TEST_PROTECTED_KEY_PATH"] = os.path.join(_test_dir, ".db.key.dpapi")
for _name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
    os.environ.pop(_name, None)
