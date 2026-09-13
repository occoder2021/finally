"""Watchlist CRUD and the tracked-ticker union."""

from __future__ import annotations

from uuid import uuid4

from .connection import get_connection
from .errors import ApiError
from .money import is_zero_qty
from .tickers import normalize_ticker
from .util import now_iso

WATCHLIST_MAX = 25


def get_watchlist(user_id: str = "default") -> list[str]:
    """Watched tickers, upper-cased, in the order they were added."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
            (user_id,),
        ).fetchall()
    return [row["ticker"] for row in rows]


def add_to_watchlist(ticker: str, user_id: str = "default") -> str:
    """Add a ticker to the watchlist. Returns the normalized ticker.

    Raises ApiError: INVALID_TICKER (bad format), WATCHLIST_FULL (already at
    the 25-ticker cap), DUPLICATE_TICKER (already watched).
    """
    normalized = normalize_ticker(ticker)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        committed = False
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM watchlist WHERE user_id = ?", (user_id,)
            ).fetchone()["n"]
            if count >= WATCHLIST_MAX:
                raise ApiError(
                    "WATCHLIST_FULL", f"Watchlist is full (maximum {WATCHLIST_MAX} tickers)."
                )
            existing = conn.execute(
                "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?",
                (user_id, normalized),
            ).fetchone()
            if existing:
                raise ApiError("DUPLICATE_TICKER", f"{normalized} is already on your watchlist.")
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid4()), user_id, normalized, now_iso()),
            )
            conn.execute("COMMIT")
            committed = True
        finally:
            if not committed:
                conn.execute("ROLLBACK")
    return normalized


def remove_from_watchlist(ticker: str, user_id: str = "default") -> None:
    """Remove a ticker from the watchlist. Raises ApiError(TICKER_NOT_FOUND)
    if it wasn't there. Does not touch positions -- a held ticker keeps its
    price via `get_tracked_tickers` even after this call."""
    normalized = normalize_ticker(ticker)
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, normalized)
        )
        if cursor.rowcount == 0:
            raise ApiError("TICKER_NOT_FOUND", f"{normalized} is not on your watchlist.")


def get_tracked_tickers(user_id: str = "default") -> list[str]:
    """The tracked ticker set: watchlist UNION tickers with a non-zero
    position. Watchlist tickers come first, in watchlist order; any
    held-but-unwatched tickers are appended after, so removing a held ticker
    from the watchlist never drops its price tracking."""
    watchlist = get_watchlist(user_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker, quantity FROM positions WHERE user_id = ?", (user_id,)
        ).fetchall()
    held = [row["ticker"] for row in rows if not is_zero_qty(row["quantity"])]
    seen = set(watchlist)
    tracked = list(watchlist)
    for ticker in held:
        if ticker not in seen:
            tracked.append(ticker)
            seen.add(ticker)
    return tracked
