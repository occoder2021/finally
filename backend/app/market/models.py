"""Data models for market data."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    day_open: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from the previous tick."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Tick-over-tick percentage change."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def day_change_percent(self) -> float:
        """Percentage change from the day-open (seed) reference price.

        This is the figure the UI labels "session change" — it is measured
        against the session-open price, never against the previous tick.
        """
        if self.day_open == 0:
            return 0.0
        return round((self.price - self.day_open) / self.day_open * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat', based on tick-over-tick change."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize to the wire shape used by SSE (matches PLAN.md 6 field names)."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.previous_price,
            "day_open": self.day_open,
            "change_pct": self.day_change_percent,
            "timestamp": self.timestamp,
            "direction": self.direction,
        }
