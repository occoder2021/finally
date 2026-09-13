"""Deterministic mock mode, entered only when `LLM_MOCK=true`.

Per TEAM_CONTRACT.md §7, mock mode must be deterministic AND still exercise
the real execution path (E2E tests depend on this): it returns a normal
`ChatStructuredResponse`, which the router runs through the exact same
`execute_trades` / `execute_watchlist_changes` path a real model response
would.
"""

from __future__ import annotations

import re

from .schema import ChatStructuredResponse, TradeRequest, WatchlistChangeRequest

_TRADE_RE = re.compile(r"\b(buy|sell)\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,5})\b", re.IGNORECASE)
_ADD_RE = re.compile(r"\badd\s+([A-Za-z]{1,5})\s+to\s+(?:the\s+)?watchlist\b", re.IGNORECASE)
_REMOVE_RE = re.compile(r"\bremove\s+([A-Za-z]{1,5})\s+from\s+(?:the\s+)?watchlist\b", re.IGNORECASE)


def mock_response(
    user_message: str,
    *,
    cash_balance: float,
    position_count: int,
) -> ChatStructuredResponse:
    """Build a deterministic structured response for the given message
    without calling any LLM provider.

    "buy N TICKER" / "sell N TICKER" (any case, anywhere in the message,
    multiple allowed) produce trade actions. "add TICKER to watchlist" /
    "remove TICKER from watchlist" produce watchlist actions. Anything else
    is a canned analysis reply built from the real portfolio numbers passed
    in, so it's deterministic for a given state without being a fixed string.
    """
    trades = [
        TradeRequest(ticker=ticker.upper(), side=side.lower(), quantity=float(qty))
        for side, qty, ticker in _TRADE_RE.findall(user_message)
    ]
    watchlist_changes = [
        WatchlistChangeRequest(ticker=ticker.upper(), action="add")
        for ticker in _ADD_RE.findall(user_message)
    ] + [
        WatchlistChangeRequest(ticker=ticker.upper(), action="remove")
        for ticker in _REMOVE_RE.findall(user_message)
    ]

    if trades or watchlist_changes:
        parts = []
        if trades:
            parts.append(", ".join(f"{t.side} {t.quantity:g} {t.ticker}" for t in trades))
        if watchlist_changes:
            parts.append(", ".join(f"{c.action} {c.ticker}" for c in watchlist_changes))
        message = "Mock: executing " + "; ".join(parts) + "."
    else:
        message = (
            f"Mock analysis: cash balance is ${cash_balance:,.2f} across "
            f"{position_count} open position{'s' if position_count != 1 else ''}."
        )

    return ChatStructuredResponse(message=message, trades=trades, watchlist_changes=watchlist_changes)
