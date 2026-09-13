"""GET/POST /api/watchlist, DELETE /api/watchlist/{ticker}."""

from __future__ import annotations

import app.db as db
from app.market import PriceCache

DEFAULT_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]


class TestGetWatchlist:
    def test_returns_seeded_tickers_no_prices(self, client, db_path):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        assert resp.json() == {"tickers": DEFAULT_TICKERS}


class TestPostWatchlist:
    def test_add_normalizes_and_tracks(self, client, db_path, market_source):
        resp = client.post("/api/watchlist", json={"ticker": "pypl"})
        assert resp.status_code == 201
        assert resp.json() == {"ticker": "PYPL"}
        assert "PYPL" in db.get_watchlist()
        assert "PYPL" in market_source.added

    def test_duplicate_ticker_rejected(self, client, db_path):
        resp = client.post("/api/watchlist", json={"ticker": "AAPL"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "DUPLICATE_TICKER"

    def test_invalid_ticker_rejected(self, client, db_path):
        resp = client.post("/api/watchlist", json={"ticker": "not a ticker!"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_TICKER"

    def test_watchlist_full(self, client, db_path):
        # Seed already has 10; fill up to the 25 cap directly through the db
        # layer (bypassing the API) so this test stays fast and focused on
        # the boundary behavior, not on adding 15 tickers one at a time.
        extra = [f"Z{chr(65 + i)}" for i in range(15)]  # ZA, ZB, ... ZO -- valid letters-only tickers
        for ticker in extra:
            db.add_to_watchlist(ticker)
        assert len(db.get_watchlist()) == 25

        resp = client.post("/api/watchlist", json={"ticker": "ZZZZZ"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "WATCHLIST_FULL"


class TestDeleteWatchlist:
    def test_remove_untracked_ticker_stops_tracking(self, client, db_path, market_source):
        resp = client.delete("/api/watchlist/AAPL")
        assert resp.status_code == 204
        assert "AAPL" not in db.get_watchlist()
        assert "AAPL" in market_source.removed

    def test_remove_held_ticker_keeps_price_tracking(
        self, client, db_path, market_source, price_cache: PriceCache
    ):
        price_cache.update("AAPL", 190.0)
        db.execute_trade(ticker="AAPL", side="buy", quantity=1, price=190.0)

        resp = client.delete("/api/watchlist/AAPL")
        assert resp.status_code == 204
        assert "AAPL" not in db.get_watchlist()
        # Still an open position -> get_tracked_tickers() still includes it,
        # so the market source must NOT be told to stop tracking it.
        assert "AAPL" not in market_source.removed
        assert "AAPL" in db.get_tracked_tickers()

    def test_remove_unknown_ticker_not_found(self, client, db_path):
        resp = client.delete("/api/watchlist/ZZZZ")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "TICKER_NOT_FOUND"

    def test_remove_is_case_insensitive(self, client, db_path, market_source):
        resp = client.delete("/api/watchlist/aapl")
        assert resp.status_code == 204
        assert "AAPL" not in db.get_watchlist()
