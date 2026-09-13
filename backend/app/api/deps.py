"""FastAPI dependency providers for the database layer.

`backend/app/db/` is owned by the db-engineer and is built in parallel with
this package. Route modules depend on it through `get_db_module` (a FastAPI
dependency) rather than a top-level `from app.db import ...`, for two reasons:

  - this package, and every test that imports it, loads cleanly even before
    `app/db/` exists.
  - unit tests can replace the entire database layer with a fake via
    `app.dependency_overrides[get_db_module] = lambda: fake_db`, with zero
    coupling to a real SQLite file or the db-engineer's landing schedule.

In production the import inside `get_db_module` runs once per call, but
Python caches successful imports in `sys.modules`, so after the first
request it is a cheap dict lookup, not a re-execution of `app/db/__init__.py`.
"""

from __future__ import annotations

from types import ModuleType


def get_db_module() -> ModuleType:
    """Return the `app.db` module (lazy import; see module docstring)."""
    import app.db as db

    return db
