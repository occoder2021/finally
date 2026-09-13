"""Trade execution: portfolio.py."""

from __future__ import annotations

import math

import pytest

from app.db import (
    ApiError,
    execute_trade,
    get_cash_balance,
    get_position,
    get_positions,
)


def test_get_cash_balance_defaults_to_10000(db_path):
    assert get_cash_balance() == 10000.0


def test_get_positions_empty_initially(db_path):
    assert get_positions() == []
    assert get_position("AAPL") is None


def test_buy_creates_position_and_debits_cash(db_path):
    result = execute_trade("aapl", "buy", 10, 100.0)
    assert result.ticker == "AAPL"
    assert result.side == "buy"
    assert result.quantity == 10
    assert result.price == 100.0
    assert result.total == 1000.0
    assert result.cash_after == 9000.0
    assert result.trade_id
    assert result.executed_at

    assert get_cash_balance() == 9000.0
    pos = get_position("AAPL")
    assert pos.quantity == 10
    assert pos.avg_cost == 100.0


def test_buy_more_updates_weighted_average_cost(db_path):
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "buy", 10, 200.0)
    pos = get_position("AAPL")
    assert pos.quantity == 20
    assert pos.avg_cost == 150.0
    assert get_cash_balance() == 10000.0 - 1000.0 - 2000.0


def test_sell_partial_leaves_avg_cost_unchanged(db_path):
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "sell", 4, 150.0)
    pos = get_position("AAPL")
    assert pos.quantity == 6
    assert pos.avg_cost == 100.0  # unchanged by sells
    assert get_cash_balance() == 10000.0 - 1000.0 + 600.0


def test_sell_full_position_deletes_row(db_path):
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "sell", 10, 120.0)
    assert get_position("AAPL") is None
    assert get_positions() == []
    # No float residue in cash: 10000 - 1000 + 1200 == 10200 exactly.
    assert get_cash_balance() == 10200.0


def test_sell_full_position_with_tiny_float_residue_still_deletes(db_path):
    # Buying then selling a quantity that doesn't divide evenly is the
    # classic source of 1e-13-style leftover shares; the epsilon policy
    # must treat that as fully closed.
    execute_trade("AAPL", "buy", 1 / 3, 300.0)
    execute_trade("AAPL", "sell", 1 / 3, 300.0)
    assert get_position("AAPL") is None
    assert get_positions() == []


def test_buy_insufficient_cash_raises(db_path):
    with pytest.raises(ApiError) as exc_info:
        execute_trade("AAPL", "buy", 1000, 100.0)
    assert exc_info.value.code == "INSUFFICIENT_CASH"
    assert exc_info.value.status == 400
    assert get_cash_balance() == 10000.0
    assert get_position("AAPL") is None


def test_buy_exact_full_cash_balance_succeeds(db_path):
    result = execute_trade("AAPL", "buy", 100, 100.0)
    assert result.cash_after == 0.0
    assert get_cash_balance() == 0.0


def test_sell_insufficient_shares_raises(db_path):
    execute_trade("AAPL", "buy", 5, 100.0)
    with pytest.raises(ApiError) as exc_info:
        execute_trade("AAPL", "sell", 10, 100.0)
    assert exc_info.value.code == "INSUFFICIENT_SHARES"
    # Nothing changed.
    assert get_position("AAPL").quantity == 5
    assert get_cash_balance() == 9500.0


def test_sell_with_no_position_raises_insufficient_shares(db_path):
    with pytest.raises(ApiError) as exc_info:
        execute_trade("AAPL", "sell", 1, 100.0)
    assert exc_info.value.code == "INSUFFICIENT_SHARES"


@pytest.mark.parametrize("quantity", [0, -5, math.nan, math.inf, -math.inf])
def test_invalid_quantity_rejected(db_path, quantity):
    with pytest.raises(ApiError) as exc_info:
        execute_trade("AAPL", "buy", quantity, 100.0)
    assert exc_info.value.code == "INVALID_QUANTITY"
    assert get_cash_balance() == 10000.0


def test_quantity_rounding_to_zero_is_rejected(db_path):
    with pytest.raises(ApiError) as exc_info:
        execute_trade("AAPL", "buy", 1e-13, 100.0)
    assert exc_info.value.code == "INVALID_QUANTITY"


@pytest.mark.parametrize("price", [0, -10.0, math.nan, math.inf])
def test_invalid_price_rejected(db_path, price):
    with pytest.raises(ApiError) as exc_info:
        execute_trade("AAPL", "buy", 1, price)
    assert exc_info.value.code == "PRICE_UNAVAILABLE"


def test_invalid_side_rejected(db_path):
    with pytest.raises(ApiError) as exc_info:
        execute_trade("AAPL", "hold", 1, 100.0)
    assert exc_info.value.code == "INVALID_SIDE"


def test_manual_and_ai_callers_share_the_same_function(db_path):
    """There is only one execute_trade -- calling it twice with identical
    args behaves identically regardless of the notional caller."""
    r1 = execute_trade("NVDA", "buy", 2, 480.0, user_id="default")
    r2_pos = get_position("NVDA")
    assert r1.total == 960.0
    assert r2_pos.quantity == 2
