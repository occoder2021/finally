"""Price history endpoint — seeds the frontend chart on ticker selection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .history import PriceHistoryBuffer


def create_history_router(history: PriceHistoryBuffer) -> APIRouter:
    """Create the price history router bound to a PriceHistoryBuffer.

    The factory pattern lets us inject the buffer without module-level globals,
    and keeps the route thin — all retention logic lives in the buffer.
    """
    router = APIRouter(prefix="/api/prices", tags=["prices"])

    @router.get("/{ticker}/history")
    async def get_price_history(ticker: str) -> dict:
        """Recent price points for a ticker, oldest first.

        The frontend fetches this once when a ticker is selected, renders it,
        then appends live points as SSE events arrive — no polling.
        """
        symbol = ticker.upper().strip()
        points = history.get(symbol)
        if not points:
            raise HTTPException(status_code=404, detail=f"No history for {symbol}")
        return {"ticker": symbol, "points": points}

    return router
