"""Watchlist CRUD and tracked-ticker union: watchlist.py."""

from __future__ import annotations

import pytest

from app.db import (
    WATCHLIST_MAX,
    ApiError,
    add_to_watchlist,
    execute_trade,
    get_tracked_tickers,
    get_watchlist,
    remove_from_watchlist,
)
from app.db.connection import DEFAULT_TICKERS


def test_default_seed_watchlist(db_path):
    assert get_watchlist() == DEFAULT_TICKERS


def test_add_normalizes_and_appends(db_path):
    ticker = add_to_watchlist("pypl")
    assert ticker == "PYPL"
    assert get_watchlist()[-1] == "PYPL"


def test_add_duplicate_rejected(db_path):
    add_to_watchlist("PYPL")
    with pytest.raises(ApiError) as exc_info:
        add_to_watchlist("pypl")  # same ticker, different case
    assert exc_info.value.code == "DUPLICATE_TICKER"


def test_add_invalid_ticker_rejected(db_path):
    with pytest.raises(ApiError) as exc_info:
        add_to_watchlist("TOOLONG")
    assert exc_info.value.code == "INVALID_TICKER"


def test_add_respects_cap(db_path):
    # 10 seeded already; fill to the 25-ticker cap.
    letters = "BCDEFGHIJKLMNOPQRSTUVWXYZ"
    added = 0
    for letter in letters:
        if len(get_watchlist()) >= WATCHLIST_MAX:
            break
        add_to_watchlist(letter)
        added += 1
    assert len(get_watchlist()) == WATCHLIST_MAX
    with pytest.raises(ApiError) as exc_info:
        add_to_watchlist("Z")
    assert exc_info.value.code == "WATCHLIST_FULL"


def test_remove_deletes_ticker(db_path):
    remove_from_watchlist("AAPL")
    assert "AAPL" not in get_watchlist()


def test_remove_missing_ticker_raises(db_path):
    with pytest.raises(ApiError) as exc_info:
        remove_from_watchlist("PYPL")
    assert exc_info.value.code == "TICKER_NOT_FOUND"


def test_tracked_tickers_is_watchlist_by_default(db_path):
    assert get_tracked_tickers() == DEFAULT_TICKERS


def test_tracked_tickers_includes_held_ticker_removed_from_watchlist(db_path):
    execute_trade("AAPL", "buy", 5, 100.0)
    remove_from_watchlist("AAPL")
    assert "AAPL" not in get_watchlist()
    assert "AAPL" in get_tracked_tickers()


def test_tracked_tickers_excludes_closed_position(db_path):
    execute_trade("PYPL", "buy", 5, 50.0)  # not on watchlist
    assert "PYPL" in get_tracked_tickers()
    execute_trade("PYPL", "sell", 5, 50.0)
    assert "PYPL" not in get_tracked_tickers()
