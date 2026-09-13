"""Portfolio value snapshots for the P&L chart."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .connection import get_connection
from .money import round_cash
from .util import now_iso


def record_snapshot(total_value: float, user_id: str = "default") -> None:
    """Record a portfolio value snapshot. Called every 30s by a background
    task and immediately after each trade; both call sites use this same
    helper so there is exactly one snapshot writer."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (str(uuid4()), user_id, round_cash(total_value), now_iso()),
        )


def get_snapshots(limit: int = 500, user_id: str = "default") -> list[dict]:
    """Snapshots in chronological order (oldest first), capped at `limit`
    most recent. Each item is `{"total_value": float, "recorded_at": str}`."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id = ? ORDER BY recorded_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [
        {"total_value": row["total_value"], "recorded_at": row["recorded_at"]}
        for row in reversed(rows)
    ]


def prune_snapshots(days: int = 30, user_id: str = "default") -> int:
    """Delete snapshots older than `days` days. Returns the number deleted."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM portfolio_snapshots WHERE user_id = ? AND recorded_at < ?",
            (user_id, cutoff),
        )
    return cursor.rowcount
