"""Tests for `app.main`'s wiring: every subsystem's routes are mounted, the
lifespan boots market data from the tracked ticker set and runs the snapshot
task, and everything shuts down cleanly.

Uses the real module-level `price_cache`/`market_source` singletons from
`app.main` (as the app itself does), scoped by a fresh temp db per test via
the `db_path` fixture from `tests/api/conftest.py`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.db as db
import app.main as main_module
from app.main import DEFAULT_TICKERS, create_app, initial_tickers


class TestInitialTickers:
    def test_falls_back_to_default_watchlist_without_db(self, monkeypatch, db_path):
        """If app.db somehow isn't importable, boot still works via the
        documented fallback rather than crashing."""
        monkeypatch.setattr(main_module, "_try_import_db", lambda: None)
        assert initial_tickers() == DEFAULT_TICKERS

    def test_uses_tracked_tickers_from_db(self, db_path):
        """On a freshly seeded db, tracked tickers == the seeded watchlist."""
        assert set(initial_tickers()) == set(DEFAULT_TICKERS)

    def test_reflects_a_held_but_unwatched_ticker(self, db_path):
        # price_cache is the real module-level singleton (as production code
        # uses it), so this test must clean up after itself or it leaks a
        # ticker into every test that runs after it in this session.
        main_module.price_cache.update("PLTR", 25.0)
        try:
            db.execute_trade(ticker="PLTR", side="buy", quantity=1, price=25.0)
            assert "PLTR" in initial_tickers()
        finally:
            main_module.price_cache.remove("PLTR")


class TestRoutesMounted:
    def test_every_documented_endpoint_is_registered(self):
        paths = {r.path for r in create_app().routes}
        assert "/api/health" in paths
        assert "/api/stream/prices" in paths
        assert "/api/prices/{ticker}/history" in paths
        assert "/api/portfolio" in paths
        assert "/api/portfolio/trade" in paths
        assert "/api/portfolio/history" in paths
        assert "/api/watchlist" in paths
        assert "/api/watchlist/{ticker}" in paths
        assert "/api/chat" in paths
        assert "/api/chat/history" in paths


class TestLifespan:
    def test_feed_and_snapshot_task_run_during_lifespan_and_stop_after(self, db_path):
        app = create_app()
        with TestClient(app):
            assert set(main_module.market_source.get_tickers()) == set(DEFAULT_TICKERS)
            assert len(main_module.price_cache) == len(DEFAULT_TICKERS)
            assert main_module._snapshot_task is not None

        assert main_module._snapshot_task is None

    def test_health_reports_tracked_ticker_count(self, db_path):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["tracked_tickers"] == len(DEFAULT_TICKERS)
