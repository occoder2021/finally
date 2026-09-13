"""Cash, positions, and trade execution.

`execute_trade` is the single execution path for both manual trades and
LLM-initiated trades (TEAM_CONTRACT.md 5 / PLAN.md 8) -- validation and
accounting cannot diverge between the two callers because they call the
same function.
"""

from __future__ import annotations

import math
from uuid import uuid4

from .connection import get_connection
from .errors import ApiError
from .models import Position, TradeResult
from .money import QTY_EPSILON, is_zero_qty, round_cash, round_qty
from .util import now_iso

_VALID_SIDES = ("buy", "sell")


def get_cash_balance(user_id: str = "default") -> float:
    """The user's current cash balance."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
    return row["cash_balance"] if row else 0.0


def get_positions(user_id: str = "default") -> list[Position]:
    """All current holdings, ordered by ticker."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
    return [
        Position(ticker=row["ticker"], quantity=row["quantity"], avg_cost=row["avg_cost"])
        for row in rows
    ]


def get_position(ticker: str, user_id: str = "default") -> Position | None:
    """A single holding, or None if the user holds no position in it."""
    normalized = ticker.strip().upper()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, normalized),
        ).fetchone()
    if row is None:
        return None
    return Position(ticker=row["ticker"], quantity=row["quantity"], avg_cost=row["avg_cost"])


def execute_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = "default",
) -> TradeResult:
    """Execute a market order at `price` and return the resulting fill.

    `price` is supplied by the caller, which has already resolved it from
    the live price cache and raised PRICE_UNAVAILABLE if it was None -- this
    function never imports `app.market`. The cash read, the position
    read/write, the cash write, and the trade-log insert all happen inside
    one `BEGIN IMMEDIATE` transaction, so the balance/share check can never
    be invalidated by a concurrent trade between the check and the write:
    overlapping calls serialize on the write lock instead of racing.

    Buys update the position's weighted-average cost; sells leave avg_cost
    unchanged. A sell that fully closes a position DELETEs the row rather
    than leaving it at quantity = 0.

    Raises ApiError:
        INVALID_QUANTITY   -- quantity is non-positive, non-finite, or
                               rounds to zero under the quantity precision
                               policy.
        PRICE_UNAVAILABLE  -- price is non-positive or non-finite.
        INSUFFICIENT_CASH  -- a buy would cost more than the cash balance.
        INSUFFICIENT_SHARES -- a sell exceeds the held quantity.
    """
    normalized_side = (side or "").strip().lower()
    if normalized_side not in _VALID_SIDES:
        raise ApiError("INVALID_SIDE", f"Side must be 'buy' or 'sell', got {side!r}.")
    if not math.isfinite(quantity) or quantity <= 0:
        raise ApiError("INVALID_QUANTITY", f"Quantity must be a positive number, got {quantity}.")
    if not math.isfinite(price) or price <= 0:
        raise ApiError("PRICE_UNAVAILABLE", f"No usable price for {ticker}.")

    ticker = ticker.strip().upper()
    qty = round_qty(quantity)
    if is_zero_qty(qty):
        raise ApiError("INVALID_QUANTITY", f"Quantity must be a positive number, got {quantity}.")
    unit_price = round_cash(price)
    total = round_cash(qty * unit_price)
    now = now_iso()
    trade_id = str(uuid4())
    new_cash: float

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        committed = False
        try:
            profile_row = conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
            ).fetchone()
            cash = profile_row["cash_balance"] if profile_row else 0.0
            pos_row = conn.execute(
                "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            ).fetchone()
            held_qty = pos_row["quantity"] if pos_row else 0.0
            held_cost = pos_row["avg_cost"] if pos_row else 0.0

            if normalized_side == "buy":
                if total > cash + 1e-9:
                    raise ApiError(
                        "INSUFFICIENT_CASH",
                        f"Need ${total:,.2f} but only ${cash:,.2f} available.",
                    )
                new_cash = round_cash(cash - total)
                new_qty = round_qty(held_qty + qty)
                new_cost = round_cash((held_qty * held_cost + qty * unit_price) / new_qty)
                if pos_row is None:
                    conn.execute(
                        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), user_id, ticker, new_qty, new_cost, now),
                    )
                else:
                    conn.execute(
                        "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                        "WHERE user_id = ? AND ticker = ?",
                        (new_qty, new_cost, now, user_id, ticker),
                    )
            else:
                if qty > held_qty + QTY_EPSILON:
                    raise ApiError(
                        "INSUFFICIENT_SHARES",
                        f"You only own {held_qty:g} shares of {ticker}.",
                    )
                new_cash = round_cash(cash + total)
                remaining = round_qty(held_qty - qty)
                if is_zero_qty(remaining):
                    conn.execute(
                        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                        (user_id, ticker),
                    )
                else:
                    conn.execute(
                        "UPDATE positions SET quantity = ?, updated_at = ? "
                        "WHERE user_id = ? AND ticker = ?",
                        (remaining, now, user_id, ticker),
                    )

            conn.execute(
                "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_cash, user_id)
            )
            conn.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (trade_id, user_id, ticker, normalized_side, qty, unit_price, now),
            )
            conn.execute("COMMIT")
            committed = True
        finally:
            if not committed:
                conn.execute("ROLLBACK")

    return TradeResult(
        ticker=ticker,
        side=normalized_side,
        quantity=qty,
        price=unit_price,
        total=total,
        cash_after=new_cash,
        trade_id=trade_id,
        executed_at=now,
    )
