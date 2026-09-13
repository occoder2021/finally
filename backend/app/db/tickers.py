"""Ticker symbol normalization -- the one implementation every add/remove
path and trade path should route through before touching the database."""

from __future__ import annotations

import re

from .errors import ApiError

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


def normalize_ticker(raw: str) -> str:
    """Trim, upper-case, and validate a ticker symbol.

    Normalization happens before any UNIQUE(user_id, ticker) check, so
    'aapl' and ' AAPL ' collide with 'AAPL'. Raises ApiError(INVALID_TICKER)
    for anything that isn't 1-5 letters once normalized -- malformed symbols
    must never reach the watchlist or trades tables. A synthesized simulator
    price is never treated as confirmation that a symbol is real; this is a
    syntactic check only.
    """
    stripped = (raw or "").strip()
    normalized = stripped.upper()
    if not _TICKER_RE.fullmatch(normalized):
        raise ApiError("INVALID_TICKER", f"'{stripped}' is not a valid ticker symbol.")
    return normalized
