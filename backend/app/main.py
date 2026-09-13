"""FastAPI application entrypoint — wires the market data, database, API and
LLM chat subsystems together."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.api import (
    SnapshotTask,
    create_portfolio_router,
    create_watchlist_router,
    install_exception_handlers,
    mount_static,
)
from app.market import (
    MarketSinks,
    PriceCache,
    PriceHistoryBuffer,
    create_history_router,
    create_market_data_source,
    create_stream_router,
)

logger = logging.getLogger(__name__)

DEFAULT_TICKERS: list[str] = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

# Created at module scope (not inside lifespan) so route handlers elsewhere in
# the app — watchlist, trade execution — can import and call
# market_source.add_ticker(...) / price_cache.get_price(...) without threading
# FastAPI dependency injection through every layer.
price_cache = PriceCache()
price_history = PriceHistoryBuffer()
sinks = MarketSinks(price_cache, price_history)
market_source = create_market_data_source(sinks)

_snapshot_task: SnapshotTask | None = None


def _try_import_db() -> Any | None:
    """Lazily import `app.db`, returning None if it isn't available.

    `app/db/` is built in parallel by the db-engineer per TEAM_CONTRACT.md;
    this keeps `app.main` importable (and its market-only behavior testable)
    independent of build order. By the time the app actually runs, this is
    expected to succeed every time.
    """
    try:
        import app.db as db
    except ImportError:
        logger.warning("app.db is not available; starting with market data only")
        return None
    return db


def _try_create_chat_router() -> Any | None:
    """Lazily import and build the chat router; None if `app.llm` isn't ready yet."""
    try:
        from app.llm import create_chat_router
    except ImportError:
        logger.warning("app.llm is not available; /api/chat will not be mounted")
        return None
    return create_chat_router(price_cache, market_source)


def initial_tickers() -> list[str]:
    """The ticker set to start tracking at boot: the watchlist UNION tickers
    with an open position (falls back to the default watchlist if `app.db`
    isn't available yet)."""
    db = _try_import_db()
    if db is None:
        return list(DEFAULT_TICKERS)
    return db.get_tracked_tickers()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot sequence: init/prune the db, start market data for the tracked
    ticker set, start the snapshot task; reverse cleanly on shutdown."""
    global _snapshot_task

    db = _try_import_db()
    if db is not None:
        db.init_db()
        pruned = db.prune_snapshots()
        if pruned:
            logger.info("Pruned %d snapshot(s) older than 30 days", pruned)

    tickers = initial_tickers()
    await market_source.start(tickers)
    logger.info("Market data started for %d tickers", len(tickers))

    if db is not None:
        _snapshot_task = SnapshotTask(db, price_cache)
        _snapshot_task.start()

    try:
        yield
    finally:
        if _snapshot_task is not None:
            await _snapshot_task.stop()
            _snapshot_task = None
        await market_source.stop()
        logger.info("Market data stopped")


def create_app() -> FastAPI:
    """Build the FastAPI app with every subsystem's routes mounted."""
    app = FastAPI(
        title="FinAlly",
        description="AI Trading Workstation",
        version="0.1.0",
        lifespan=lifespan,
    )

    install_exception_handlers(app)

    @app.get("/api/health", tags=["system"])
    async def health() -> dict:
        """Health check for Docker/deployment."""
        return {
            "status": "ok",
            "tracked_tickers": len(price_cache),
            "source": type(market_source).__name__,
        }

    # Market data (existing, untouched).
    app.include_router(create_stream_router(price_cache))
    app.include_router(create_history_router(price_history))

    # Portfolio, watchlist.
    app.include_router(create_portfolio_router(price_cache, market_source))
    app.include_router(create_watchlist_router(market_source))

    # Chat — owned by the llm-engineer; mounted here once app.llm exists.
    chat_router = _try_create_chat_router()
    if chat_router is not None:
        app.include_router(chat_router)

    # Static frontend export. Registered last: it's a catch-all, so every
    # /api/* route above must be matched first.
    mount_static(app)

    return app


app = create_app()
