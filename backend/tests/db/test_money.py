"""Precision policy: money.py."""

from __future__ import annotations

from app.db.money import CASH_DP, QTY_DP, QTY_EPSILON, is_zero_qty, round_cash, round_qty


def test_round_cash_rounds_to_two_decimals():
    assert round_cash(9999.999999999998) == 10000.0
    assert round_cash(1.005) == round(1.005, CASH_DP)
    assert round_cash(10) == 10.0


def test_round_qty_rounds_to_eight_decimals():
    assert round_qty(1e-13) == 0.0
    assert round_qty(1.123456789) == round(1.123456789, QTY_DP)


def test_is_zero_qty_uses_epsilon():
    assert is_zero_qty(0.0) is True
    assert is_zero_qty(1e-13) is True
    assert is_zero_qty(QTY_EPSILON / 2) is True
    assert is_zero_qty(-1e-13) is True
    assert is_zero_qty(0.001) is False
    assert is_zero_qty(1.0) is False
