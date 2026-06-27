"""Test harness — isolates tests on a temp SQLite DB and seeds it once.

CRATE_DB_PATH is set *before* any `app` import so config picks it up.
"""
import os
import pathlib
import sys
import tempfile

# services/api on sys.path so `import app` works under pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

_DB = pathlib.Path(tempfile.gettempdir()) / "crate_test.db"
os.environ["CRATE_DB_PATH"] = str(_DB)
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("ADOPT_DAYS", "4")
os.environ.setdefault("ADOPT_WEEKS", "3")
# Tests must be deterministic + offline — force the stub regardless of any real
# provider key present in the developer's .env.
os.environ["LLM_PROVIDER"] = "stub"

# clean slate each session
for _suffix in ("", "-wal", "-shm"):
    try:
        pathlib.Path(str(_DB) + _suffix).unlink()
    except FileNotFoundError:
        pass

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    from app.seed import seed

    seed()
    yield
