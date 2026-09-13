"""Lazy init, idempotency, and reset behavior: connection.py."""

from __future__ import annotations

import os
import sqlite3

from app.db import get_cash_balance, get_watchlist, init_db, reset_db_for_tests
from app.db.connection import DEFAULT_TICKERS, get_connection


def test_init_db_creates_and_seeds(db_path):
    assert os.path.exists(db_path)
    assert get_cash_balance() == 10000.0
    assert get_watchlist() == DEFAULT_TICKERS


def test_init_db_is_idempotent(db_path):
    init_db(db_path)
    init_db(db_path)
    # Seeding must not duplicate rows or reset a mutated balance.
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM users_profile").fetchone()["n"]
    assert count == 1
    assert get_watchlist() == DEFAULT_TICKERS


def test_get_connection_lazily_initializes_new_path(tmp_path, monkeypatch):
    """A path that has never been touched gets schema + seed on first
    get_connection() call, without an explicit init_db() call."""
    path = str(tmp_path / "lazy.db")
    monkeypatch.setenv("FINALLY_DB_PATH", path)
    assert not os.path.exists(path)

    with get_connection() as conn:
        row = conn.execute("SELECT cash_balance FROM users_profile WHERE id='default'").fetchone()
    assert row["cash_balance"] == 10000.0


def test_get_connection_uses_wal_and_row_factory(db_path):
    with get_connection() as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        assert conn.row_factory is sqlite3.Row


def test_reset_db_for_tests_wipes_mutations(db_path):
    with get_connection() as conn:
        conn.execute("UPDATE users_profile SET cash_balance = 42.0 WHERE id = 'default'")
    assert get_cash_balance() == 42.0

    reset_db_for_tests(db_path)
    assert get_cash_balance() == 10000.0
