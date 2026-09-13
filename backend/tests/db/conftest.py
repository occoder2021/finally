"""Fixtures for the db test suite.

Every test gets its own temp-file SQLite database via `FINALLY_DB_PATH`, so
nothing here ever touches the repo's real `db/finally.db`.
"""

from __future__ import annotations

import pytest

from app.db import reset_db_for_tests


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point FINALLY_DB_PATH at a fresh temp file and reset the schema."""
    path = str(tmp_path / "test.db")
    monkeypatch.setenv("FINALLY_DB_PATH", path)
    reset_db_for_tests(path)
    return path
