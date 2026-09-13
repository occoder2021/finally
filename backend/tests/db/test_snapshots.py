"""Portfolio snapshots: snapshots.py."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db import get_snapshots, prune_snapshots, record_snapshot
from app.db.connection import get_connection


def test_record_and_get_snapshots_chronological(db_path):
    record_snapshot(10000.0)
    time.sleep(0.01)
    record_snapshot(10500.0)
    time.sleep(0.01)
    record_snapshot(10250.0)

    snapshots = get_snapshots()
    assert [s["total_value"] for s in snapshots] == [10000.0, 10500.0, 10250.0]
    # chronological: recorded_at strictly increasing
    times = [s["recorded_at"] for s in snapshots]
    assert times == sorted(times)


def test_record_snapshot_rounds_cash(db_path):
    record_snapshot(9999.999999999998)
    snapshots = get_snapshots()
    assert snapshots[0]["total_value"] == 10000.0


def test_get_snapshots_respects_limit(db_path):
    for i in range(10):
        record_snapshot(float(i))
    snapshots = get_snapshots(limit=3)
    assert len(snapshots) == 3
    # The most recent 3, still chronological.
    assert [s["total_value"] for s in snapshots] == [7.0, 8.0, 9.0]


def test_get_snapshots_caps_at_500(db_path):
    # Insert directly for speed rather than 500 real record_snapshot calls.
    base = datetime.now(timezone.utc)
    with get_connection() as conn:
        rows = [
            (str(uuid4()), "default", float(i), (base + timedelta(seconds=i)).isoformat())
            for i in range(520)
        ]
        conn.executemany(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
    snapshots = get_snapshots(limit=500)
    assert len(snapshots) == 500
    # Should be the most recent 500 (values 20..519), still chronological.
    assert snapshots[0]["total_value"] == 20.0
    assert snapshots[-1]["total_value"] == 519.0


def test_prune_snapshots_removes_old_rows(db_path):
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    recent_time = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, 'default', 1.0, ?)",
            (str(uuid4()), old_time),
        )
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, 'default', 2.0, ?)",
            (str(uuid4()), recent_time),
        )
    deleted = prune_snapshots(days=30)
    assert deleted == 1
    remaining = get_snapshots()
    assert len(remaining) == 1
    assert remaining[0]["total_value"] == 2.0
