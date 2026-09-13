"""Fixtures for the API test suite.

Every test gets a fresh temp-file SQLite database (same pattern as
`tests/db/conftest.py`) and a router-level app built from
`create_portfolio_router`/`create_watchlist_router` directly, bound to a
fresh `PriceCache` and a fake, in-memory `MarketDataSource` — no background
simulator task, no real network, fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import create_portfolio_router, create_watchlist_router, install_exception_handlers
from app.db import reset_db_for_tests
from app.market import PriceCache


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point FINALLY_DB_PATH at a fresh temp file and reset the schema."""
    path = str(tmp_path / "test.db")
    monkeypatch.setenv("FINALLY_DB_PATH", path)
    reset_db_for_tests(path)
    return path


@dataclass
class FakeMarketSource:
    """Minimal in-memory stand-in for `MarketDataSource` (duck-typed — the
    portfolio/watchlist routers only ever call `add_ticker`/`remove_ticker`).
    Tracks every call so tests can assert on tracked-set bookkeeping."""

    tickers: set[str] = field(default_factory=set)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    async def start(self, tickers: list[str]) -> None:
        self.tickers = set(tickers)

    async def stop(self) -> None:
        pass

    async def add_ticker(self, ticker: str) -> None:
        self.tickers.add(ticker)
        self.added.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.tickers.discard(ticker)
        self.removed.append(ticker)

    def get_tickers(self) -> list[str]:
        return list(self.tickers)


@pytest.fixture
def price_cache() -> PriceCache:
    return PriceCache()


@pytest.fixture
def market_source() -> FakeMarketSource:
    return FakeMarketSource()


@pytest.fixture
def app(price_cache: PriceCache, market_source: FakeMarketSource) -> FastAPI:
    fastapi_app = FastAPI()
    install_exception_handlers(fastapi_app)
    fastapi_app.include_router(create_portfolio_router(price_cache, market_source))
    fastapi_app.include_router(create_watchlist_router(market_source))
    return fastapi_app


@pytest.fixture
def client(app: FastAPI, db_path: str) -> TestClient:
    return TestClient(app)
