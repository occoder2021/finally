"""Background snapshot task (TEAM_CONTRACT §6).

Values the portfolio from the live price cache + db holdings every 30s and
records a `portfolio_snapshots` row. Runs alongside (not instead of) the
immediate post-trade snapshot taken in `portfolio.post_trade` — a trade
landing in the same second as a tick is not suppressed (PLAN.md §14, S4).
"""

from __future__ import annotations

import asyncio
import logging
from types import ModuleType

from app.market import PriceCache

from .portfolio import value_portfolio

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30.0


class SnapshotTask:
    """Owns the asyncio task for periodic portfolio snapshots.

    A thin wrapper (rather than a bare `asyncio.create_task` in the lifespan
    handler) so `start`/`stop` can be called cleanly from tests without
    reaching into `main.py`'s lifespan internals.
    """

    def __init__(
        self,
        db: ModuleType,
        price_cache: PriceCache,
        interval: float = SNAPSHOT_INTERVAL_SECONDS,
    ) -> None:
        self._db = db
        self._price_cache = price_cache
        self._interval = interval
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="portfolio-snapshot-task")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval)
                try:
                    total_value = value_portfolio(self._db, self._price_cache)
                    self._db.record_snapshot(total_value=total_value)
                except Exception:  # noqa: BLE001 - a snapshot failure must not kill the loop
                    logger.exception("Portfolio snapshot failed")
        except asyncio.CancelledError:
            raise
