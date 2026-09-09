"""Tests for the FastAPI application wiring."""

from fastapi.testclient import TestClient

from app.main import DEFAULT_TICKERS, create_app, initial_tickers, price_cache, price_history


class TestInitialTickers:
    """The boot ticker set."""

    def test_returns_the_default_watchlist(self):
        """Until the DB lands, boot tracks the documented default watchlist."""
        assert initial_tickers() == DEFAULT_TICKERS

    def test_returns_a_copy(self):
        """Callers cannot mutate the module-level default list."""
        tickers = initial_tickers()
        tickers.append("ZZZZ")
        assert "ZZZZ" not in DEFAULT_TICKERS

    def test_default_watchlist_matches_the_plan(self):
        """The ten seeded tickers from the plan."""
        assert DEFAULT_TICKERS == [
            "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
            "NVDA", "META", "JPM", "V", "NFLX",
        ]


class TestRoutes:
    """Mounted routes."""

    def test_market_routes_are_mounted(self):
        """Both the SSE stream and the history endpoint are registered."""
        paths = {r.path for r in create_app().routes}
        assert "/api/stream/prices" in paths
        assert "/api/prices/{ticker}/history" in paths
        assert "/api/health" in paths


class TestLifespan:
    """Startup and shutdown drive the market data feed."""

    def test_feed_runs_during_lifespan_and_stops_after(self):
        """Prices are flowing inside the context and the task is stopped after."""
        from app.main import market_source

        app = create_app()
        with TestClient(app) as client:
            assert set(market_source.get_tickers()) == set(DEFAULT_TICKERS)
            # start() seeds both sinks before the first tick, so data is
            # available immediately rather than after the first interval.
            assert len(price_cache) == len(DEFAULT_TICKERS)
            assert price_history.get("AAPL")

            resp = client.get("/api/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ok"
            assert body["tracked_tickers"] == len(DEFAULT_TICKERS)

        # After shutdown the background task is released
        assert market_source._task is None

    def test_history_endpoint_serves_seeded_data(self):
        """The history buffer is populated well enough to seed a chart."""
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/prices/AAPL/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "AAPL"
        assert len(body["points"]) >= 1
