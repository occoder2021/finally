"""Watchlist endpoints (TEAM_CONTRACT §6).

Keeps the market data source's tracked ticker set in sync with the db:
adding to the watchlist starts tracking the ticker; removing stops tracking
it only if `get_tracked_tickers` (watchlist UNION open positions) says
nothing else needs its price, so a held position never silently loses its
price feed.
"""

from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter, Depends, Response

from app.market import MarketDataSource

from .deps import get_db_module
from .schemas import WatchlistAddRequest


def create_watchlist_router(market_source: MarketDataSource) -> APIRouter:
    """Build the watchlist router bound to the shared market data source."""
    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

    @router.get("")
    async def get_watchlist(db: ModuleType = Depends(get_db_module)) -> dict:
        # Tickers only — prices come from SSE, so there's exactly one source
        # of truth for price and no stale flash on load.
        return {"tickers": db.get_watchlist()}

    @router.post("", status_code=201)
    async def post_watchlist(
        body: WatchlistAddRequest, db: ModuleType = Depends(get_db_module)
    ) -> dict:
        ticker = db.add_to_watchlist(body.ticker)
        await market_source.add_ticker(ticker)
        return {"ticker": ticker}

    @router.delete("/{ticker}", status_code=204)
    async def delete_watchlist(
        ticker: str, db: ModuleType = Depends(get_db_module)
    ) -> Response:
        normalized = ticker.strip().upper()
        db.remove_from_watchlist(normalized)

        # Still tracked via an open position? Leave the price feed running.
        if normalized not in db.get_tracked_tickers():
            await market_source.remove_ticker(normalized)

        return Response(status_code=204)

    return router
