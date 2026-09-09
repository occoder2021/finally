"""Bounded in-memory price history buffer, per ticker."""

from __future__ import annotations

from collections import deque
from threading import Lock

MAX_POINTS = 200


class PriceHistoryBuffer:
    """Thread-safe ring buffer of recent (timestamp, price) points per ticker.

    Written by the same call site that writes to PriceCache (see MarketSinks),
    so the two sinks never drift out of sync. Feeds
    GET /api/prices/{ticker}/history, which seeds the frontend chart on
    ticker selection.

    deque(maxlen=N) gives O(1) append with automatic eviction of the oldest
    point, so memory stays bounded no matter how long the simulator runs.
    """

    def __init__(self, max_points: int = MAX_POINTS) -> None:
        self._max_points = max_points
        self._buffers: dict[str, deque[tuple[float, float]]] = {}
        self._lock = Lock()

    @property
    def max_points(self) -> int:
        """Maximum retained points per ticker."""
        return self._max_points

    def append(self, ticker: str, price: float, timestamp: float) -> None:
        """Append one point for a ticker, evicting the oldest if full."""
        with self._lock:
            buf = self._buffers.setdefault(ticker, deque(maxlen=self._max_points))
            buf.append((timestamp, price))

    def get(self, ticker: str) -> list[dict[str, float]]:
        """Return points oldest-first: [{"timestamp": ..., "price": ...}, ...].

        An unknown ticker returns an empty list rather than raising.
        """
        with self._lock:
            buf = self._buffers.get(ticker)
            if not buf:
                return []
            return [{"timestamp": ts, "price": price} for ts, price in buf]

    def remove(self, ticker: str) -> None:
        """Drop all history for a ticker (e.g., when it stops being tracked)."""
        with self._lock:
            self._buffers.pop(ticker, None)

    def tickers(self) -> list[str]:
        """Tickers that currently have at least one recorded point."""
        with self._lock:
            return [t for t, buf in self._buffers.items() if buf]
