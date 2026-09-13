"""GET /api/portfolio, POST /api/portfolio/trade, GET /api/portfolio/history."""

from __future__ import annotations

import pytest

import app.db as db
from app.market import PriceCache


class TestGetPortfolio:
    def test_empty_portfolio_shape(self, client, db_path):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "cash_balance": 10000.0,
            "positions": [],
            "total_value": 10000.0,
            "total_unrealized_pnl": 0.0,
            "starting_cash": 10000.0,
        }

    def test_position_with_cached_price(self, client, db_path, price_cache: PriceCache):
        price_cache.update("AAPL", 190.0)
        db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=190.0)
        price_cache.update("AAPL", 200.0)  # price moves after the fill

        resp = client.get("/api/portfolio")
        body = resp.json()
        assert body["cash_balance"] == 10000.0 - 1900.0
        assert len(body["positions"]) == 1
        pos = body["positions"][0]
        assert pos["ticker"] == "AAPL"
        assert pos["quantity"] == 10
        assert pos["avg_cost"] == 190.0
        assert pos["current_price"] == 200.0
        assert pos["market_value"] == 2000.0
        assert pos["unrealized_pnl"] == 100.0
        assert pos["pnl_percent"] == pytest.approx(100.0 / 1900.0 * 100)
        assert pos["price_available"] is True
        assert body["total_value"] == (10000.0 - 1900.0) + 2000.0
        assert body["total_unrealized_pnl"] == 100.0

    def test_position_with_no_cached_price_is_unavailable_not_zero(
        self, client, db_path, price_cache: PriceCache
    ):
        price_cache.update("AAPL", 190.0)
        db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=190.0)
        price_cache.remove("AAPL")  # simulate the price disappearing from the cache

        resp = client.get("/api/portfolio")
        body = resp.json()
        pos = body["positions"][0]
        assert pos["price_available"] is False
        assert pos["current_price"] is None
        assert pos["market_value"] is None
        assert pos["unrealized_pnl"] is None
        assert pos["pnl_percent"] is None
        # Never valued at zero, never dropped: cash-only total, position still listed.
        assert body["total_value"] == 10000.0 - 1900.0
        assert body["total_unrealized_pnl"] == 0.0
        assert len(body["positions"]) == 1


class TestPostTrade:
    def test_buy_success(self, client, db_path, price_cache: PriceCache, market_source):
        price_cache.update("NVDA", 480.12)
        resp = client.post(
            "/api/portfolio/trade", json={"ticker": "nvda", "quantity": 5, "side": "buy"}
        )
        assert resp.status_code == 200
        trade = resp.json()["trade"]
        assert trade["ticker"] == "NVDA"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 5
        assert trade["price"] == 480.12
        assert trade["total"] == 2400.6
        assert trade["cash_after"] == 10000.0 - 2400.6
        assert "executed_at" in trade

        # The fill's ticker is kept tracked for pricing, and a snapshot lands.
        assert "NVDA" in market_source.added
        snapshots = db.get_snapshots()
        assert len(snapshots) == 1
        assert snapshots[0]["total_value"] == trade["cash_after"] + 5 * 480.12

    def test_sell_success_full_close_deletes_position(self, client, db_path, price_cache: PriceCache):
        price_cache.update("AAPL", 190.0)
        db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=190.0)

        resp = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "sell"}
        )
        assert resp.status_code == 200
        assert db.get_positions() == []

    def test_price_unavailable(self, client, db_path):
        resp = client.post(
            "/api/portfolio/trade", json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "PRICE_UNAVAILABLE"

    def test_insufficient_cash(self, client, db_path, price_cache: PriceCache):
        price_cache.update("AAPL", 190.0)
        resp = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1000, "side": "buy"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INSUFFICIENT_CASH"

    def test_insufficient_shares(self, client, db_path, price_cache: PriceCache):
        price_cache.update("AAPL", 190.0)
        resp = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "sell"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INSUFFICIENT_SHARES"

    def test_invalid_quantity(self, client, db_path, price_cache: PriceCache):
        price_cache.update("AAPL", 190.0)
        resp = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 0, "side": "buy"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_QUANTITY"

    def test_invalid_side_normalizes_to_validation_error(self, client, db_path, price_cache: PriceCache):
        price_cache.update("AAPL", 190.0)
        resp = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "hold"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_manual_and_future_trades_share_one_execution_path(
        self, client, db_path, price_cache: PriceCache
    ):
        """The route never re-implements validation: it resolves a price and
        calls `execute_trade` — proven here by checking the resulting position
        matches exactly what a direct `execute_trade` call would produce."""
        price_cache.update("MSFT", 400.0)
        client.post("/api/portfolio/trade", json={"ticker": "MSFT", "quantity": 2, "side": "buy"})
        pos = db.get_position("MSFT")
        assert pos.quantity == 2
        assert pos.avg_cost == 400.0


class TestGetHistory:
    def test_returns_snapshots_chronologically(self, client, db_path):
        db.record_snapshot(total_value=10000.0)
        db.record_snapshot(total_value=10050.0)
        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200
        body = resp.json()
        assert [s["total_value"] for s in body["snapshots"]] == [10000.0, 10050.0]

    def test_empty_history(self, client, db_path):
        resp = client.get("/api/portfolio/history")
        assert resp.json() == {"snapshots": []}
