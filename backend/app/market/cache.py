"""Thread-safe in-memory price cache."""

from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (exactly one at a time,
    selected by the factory). Readers: SSE endpoint, portfolio valuation,
    trade execution, watchlist endpoint.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._day_open: dict[str, float] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonic; bumped on every update, drives SSE change detection

    def set_day_open(self, ticker: str, price: float) -> None:
        """Record the day-open reference price for a ticker.

        Called once, at source start or when a ticker is first added. Uses
        setdefault semantics so "first price wins" and repeated calls are
        idempotent — the reference must survive for the life of the process.
        """
        with self._lock:
            self._day_open.setdefault(ticker, round(price, 2))

    def get_day_open(self, ticker: str) -> float | None:
        """The recorded day-open reference price, or None if never set."""
        with self._lock:
            return self._day_open.get(ticker)

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Computes direction/change from the previous price, and change vs. the
        stored day-open. If no day-open is recorded yet, this price becomes it.
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price
            day_open = self._day_open.setdefault(ticker, round(price, 2))

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                day_open=day_open,
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy (safe to
        iterate without holding the lock)."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: get just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (e.g., when removed from watchlist)."""
        with self._lock:
            self._prices.pop(ticker, None)
            self._day_open.pop(ticker, None)

    @property
    def version(self) -> int:
        """Monotonic counter — SSE uses this to avoid re-serializing/pushing
        when nothing changed."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
