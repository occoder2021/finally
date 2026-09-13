"""Precision policy for money and share quantities.

Single source of truth per TEAM_CONTRACT.md 3. Applies everywhere cash or
fractional shares are written or compared: `execute_trade`, positions,
watchlist-adjacent code, and any future caller in the api/llm layers.
"""

from __future__ import annotations

QTY_EPSILON = 1e-9  # |quantity| < QTY_EPSILON => the position is closed
CASH_DP = 2  # cash is rounded to 2dp on every write
QTY_DP = 8  # quantity is rounded to 8dp on every write


def round_cash(x: float) -> float:
    """Round a dollar amount to the 2dp cash precision policy."""
    return round(x, CASH_DP)


def round_qty(x: float) -> float:
    """Round a share quantity to the 8dp quantity precision policy."""
    return round(x, QTY_DP)


def is_zero_qty(x: float) -> bool:
    """True when a quantity is small enough to treat the position as closed.

    A fully closed position is deleted, never left at quantity = 0 -- callers
    use this to decide between DELETE and UPDATE.
    """
    return abs(x) < QTY_EPSILON
