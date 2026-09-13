"""The 30s portfolio snapshot background task."""

from __future__ import annotations

import asyncio

import pytest

import app.db as db
from app.api.background import SnapshotTask
from app.market import PriceCache


@pytest.mark.asyncio
async def test_snapshot_task_records_periodically(db_path):
    price_cache = PriceCache()
    price_cache.update("AAPL", 190.0)
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=190.0)

    task = SnapshotTask(db, price_cache, interval=0.05)
    task.start()
    try:
        await asyncio.sleep(0.17)  # ~3 ticks
    finally:
        await task.stop()

    snapshots = db.get_snapshots()
    assert len(snapshots) >= 2
    expected_value = db.get_cash_balance() + 10 * 190.0
    assert snapshots[-1]["total_value"] == expected_value


@pytest.mark.asyncio
async def test_snapshot_task_does_not_suppress_post_trade_snapshot_in_same_second(db_path):
    """A trade's own immediate snapshot and a background tick landing in the
    same second must both be recorded -- no dedup by wall-clock second."""
    price_cache = PriceCache()
    task = SnapshotTask(db, price_cache, interval=0.02)
    task.start()
    try:
        db.record_snapshot(total_value=10000.0)  # simulates the trade route's own write
        await asyncio.sleep(0.07)
    finally:
        await task.stop()

    assert len(db.get_snapshots()) >= 2


@pytest.mark.asyncio
async def test_stop_is_idempotent_and_cancels_cleanly(db_path):
    price_cache = PriceCache()
    task = SnapshotTask(db, price_cache, interval=10.0)
    task.start()
    await task.stop()
    await task.stop()  # must not raise
