"""FastAPI application entrypoint — wires the market data subsystem."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


def initial_tickers() -> list[str]:
    """The ticker set to start tracking at boot.

    Per the design, tracking must cover the union of watchlist tickers and
    tickers with an open position, so a held ticker removed from the watchlist
    never loses its price. That union is owned by the API/routes layer, which
    is the only part of the app that queries the database; `app.market` just
    tracks whatever set it is told to.

    The database layer does not exist yet, so this returns the default
    watchlist. Once it lands, this is the single call site to replace with the
    watchlist-union-positions query.
    """
    return list(DEFAULT_TICKERS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the market data feed on boot, stop it cleanly on shutdown."""
    tickers = initial_tickers()
    await market_source.start(tickers)
    logger.info("Market data started for %d tickers", len(tickers))
    try:
        yield
    finally:
        await market_source.stop()
        logger.info("Market data stopped")


def create_app() -> FastAPI:
    """Build the FastAPI app with the market data routes mounted."""
    app = FastAPI(
        title="FinAlly",
        description="AI Trading Workstation",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/api/health", tags=["system"])
    async def health() -> dict:
        """Health check for Docker/deployment."""
        return {
            "status": "ok",
            "tracked_tickers": len(price_cache),
            "source": type(market_source).__name__,
        }

    app.include_router(create_stream_router(price_cache))
    app.include_router(create_history_router(price_history))
    return app


app = create_app()
