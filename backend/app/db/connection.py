"""SQLite schema, lazy initialization, and connection management.

The database path comes from env `FINALLY_DB_PATH`, defaulting to
`db/finally.db` relative to the backend working directory (the container
sets it to `/app/db/finally.db`). On first use for a given path, the schema
is created and default data seeded if missing -- no separate migration step.

Concurrency: the 30s snapshot task writes while request handlers read and
write. Each `get_connection()` call opens its own short-lived connection in
WAL mode with a generous `busy_timeout`, in autocommit mode
(`isolation_level=None`) so a lone statement commits immediately and a
multi-statement writer explicitly brackets its work in
`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`. `BEGIN IMMEDIATE` acquires the
write lock up front (rather than on the first write statement), so the
balance/share check inside a transaction can never be invalidated by another
writer between the check and the write.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .util import now_iso

_ENV_VAR = "FINALLY_DB_PATH"
_DEFAULT_DB_PATH = "db/finally.db"

DEFAULT_TICKERS: list[str] = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_user_time ON trades (user_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_user_time ON portfolio_snapshots (user_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_messages (user_id, created_at);
"""

_init_lock = threading.Lock()
_initialized_paths: set[str] = set()


def _resolve_path() -> str:
    """The configured SQLite file path, read fresh from the environment on
    every call so tests can point FINALLY_DB_PATH at a temp file per test."""
    return os.environ.get(_ENV_VAR, _DEFAULT_DB_PATH)


def _connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM users_profile WHERE id = 'default'").fetchone():
        return
    now = now_iso()
    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES ('default', 10000.0, ?)",
        (now,),
    )
    conn.executemany(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', ?, ?)",
        [(str(uuid4()), ticker, now) for ticker in DEFAULT_TICKERS],
    )


def init_db(path: str | None = None) -> None:
    """Create the schema and seed default data if missing.

    Idempotent and safe to call repeatedly, including from multiple
    threads/processes: table creation is IF NOT EXISTS, and the seed check
    is a check-then-insert wrapped in its own BEGIN IMMEDIATE transaction
    guarded by a process-local lock.
    """
    target = path or _resolve_path()
    with _init_lock:
        conn = _connect(target)
        try:
            conn.executescript(_SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            committed = False
            try:
                _seed_if_empty(conn)
                conn.execute("COMMIT")
                committed = True
            finally:
                if not committed:
                    conn.execute("ROLLBACK")
        finally:
            conn.close()
        _initialized_paths.add(target)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """A short-lived connection to the configured database, lazily
    initializing (schema + seed) the first time this path is used. Closed
    automatically when the `with` block exits.

    The connection is opened in autocommit mode (`isolation_level=None`), so
    a single statement with no explicit BEGIN commits immediately. Callers
    that need an atomic multi-statement write issue their own
    `conn.execute("BEGIN IMMEDIATE")` / `COMMIT` / `ROLLBACK`.
    """
    target = _resolve_path()
    if target not in _initialized_paths:
        init_db(target)
    conn = _connect(target)
    try:
        yield conn
    finally:
        conn.close()


def reset_db_for_tests(path: str | None = None) -> None:
    """Test-only: wipe and recreate the database at `path` (or the current
    FINALLY_DB_PATH). Deletes the file plus its -wal/-shm siblings so each
    test starts from a clean, freshly-seeded database. Never call this
    against the real `db/finally.db`."""
    target = path or _resolve_path()
    _initialized_paths.discard(target)
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(target + suffix)
        if candidate.exists():
            candidate.unlink()
    init_db(target)
