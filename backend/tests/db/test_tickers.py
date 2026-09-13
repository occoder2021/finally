"""Ticker normalization: tickers.py."""

from __future__ import annotations

import pytest

from app.db.errors import ApiError
from app.db.tickers import normalize_ticker


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("aapl", "AAPL"),
        ("AAPL", "AAPL"),
        ("  pypl  ", "PYPL"),
        ("a", "A"),
        ("abcde", "ABCDE"),
    ],
)
def test_valid_tickers_normalize(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "abcdef",  # too long
        "AB1",  # digit
        "A B",  # internal space
        "$AAPL",
        "aa-pl",
    ],
)
def test_invalid_tickers_rejected(raw):
    with pytest.raises(ApiError) as exc_info:
        normalize_ticker(raw)
    assert exc_info.value.code == "INVALID_TICKER"
    assert exc_info.value.status == 400
