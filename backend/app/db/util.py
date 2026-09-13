"""Small internal helpers shared across the db package."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string -- the timestamp format used
    by every table in the schema."""
    return datetime.now(timezone.utc).isoformat()
