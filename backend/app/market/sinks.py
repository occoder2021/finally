"""Bundles the price cache and history buffer behind a single write call."""

from __future__ import annotations

import time

from .cache import PriceCache
from .history import PriceHistoryBuffer
from .models import PriceUpdate


class MarketSinks:
    """Bundles PriceCache + PriceHistoryBuffer so data sources write to both
    atomically from the caller's point of view, with one call.

    Data sources call record()/remove() rather than touching the two sinks
    separately, which is what guarantees the "latest price" and the "recent
    series" can never disagree about a tick.
    """

    def __init__(self, cache: PriceCache, history: PriceHistoryBuffer) -> None:
        self.cache = cache
        self.history = history

    def record(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record one price into both sinks, sharing one timestamp."""
        ts = timestamp or time.time()
        update = self.cache.update(ticker=ticker, price=price, timestamp=ts)
        # Use the cache's rounded price so both sinks agree to the cent.
        self.history.append(ticker=ticker, price=update.price, timestamp=ts)
        return update

    def remove(self, ticker: str) -> None:
        """Drop a ticker from both sinks."""
        self.cache.remove(ticker)
        self.history.remove(ticker)
