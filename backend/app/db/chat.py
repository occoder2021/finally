"""Chat conversation history, including recorded action outcomes."""

from __future__ import annotations

import json
from uuid import uuid4

from .connection import get_connection
from .models import ChatMessage
from .util import now_iso


def get_chat_messages(limit: int = 50, user_id: str = "default") -> list[ChatMessage]:
    """Recent conversation in chronological order (oldest first), capped at
    `limit` most recent messages."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, role, content, actions, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [
        ChatMessage(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            actions=json.loads(row["actions"]) if row["actions"] else None,
            created_at=row["created_at"],
        )
        for row in reversed(rows)
    ]


def append_chat_message(
    role: str,
    content: str,
    actions: list[dict] | None = None,
    user_id: str = "default",
) -> ChatMessage:
    """Persist one message. `actions` (trades/watchlist changes executed, or
    None for a user message) is stored as JSON and parsed back on read."""
    msg_id = str(uuid4())
    created_at = now_iso()
    actions_json = json.dumps(actions) if actions is not None else None
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, user_id, role, content, actions_json, created_at),
        )
    return ChatMessage(
        id=msg_id, role=role, content=content, actions=actions, created_at=created_at
    )
