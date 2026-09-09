"""Tests for the price history endpoint."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.market.history import PriceHistoryBuffer
from app.market.prices_route import create_history_router


def _client(history: PriceHistoryBuffer) -> TestClient:
    app = FastAPI()
    app.include_router(create_history_router(history))
    return TestClient(app)


class TestPriceHistoryEndpoint:
    """GET /api/prices/{ticker}/history"""

    def test_returns_points_oldest_first(self):
        """Points come back in chronological order."""
        history = PriceHistoryBuffer()
        for i in range(5):
            history.append("AAPL", 190.0 + i, float(i))

        resp = _client(history).get("/api/prices/AAPL/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "AAPL"
        assert [p["price"] for p in body["points"]] == [190.0, 191.0, 192.0, 193.0, 194.0]
        assert [p["timestamp"] for p in body["points"]] == [0.0, 1.0, 2.0, 3.0, 4.0]

    def test_404_when_no_history_yet(self):
        """A ticker with no recorded points is a 404, not an empty 200."""
        resp = _client(PriceHistoryBuffer()).get("/api/prices/AAPL/history")

        assert resp.status_code == 404
        assert "AAPL" in resp.json()["detail"]

    def test_ticker_is_normalized_to_uppercase(self):
        """Lower-case requests resolve to the stored upper-case ticker."""
        history = PriceHistoryBuffer()
        history.append("AAPL", 190.0, 1.0)

        resp = _client(history).get("/api/prices/aapl/history")

        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

    def test_point_count_never_exceeds_max(self):
        """The endpoint inherits the buffer's cap."""
        history = PriceHistoryBuffer(max_points=10)
        for i in range(100):
            history.append("AAPL", float(i), float(i))

        body = _client(history).get("/api/prices/AAPL/history").json()

        assert len(body["points"]) == 10
        assert body["points"][0]["price"] == 90.0

    def test_unrelated_ticker_not_returned(self):
        """History is per ticker."""
        history = PriceHistoryBuffer()
        history.append("AAPL", 190.0, 1.0)

        assert _client(history).get("/api/prices/TSLA/history").status_code == 404
