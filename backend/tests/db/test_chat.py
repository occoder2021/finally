"""Chat message round-tripping: chat.py."""

from __future__ import annotations

from app.db import append_chat_message, get_chat_messages


def test_append_and_get_round_trips(db_path):
    append_chat_message("user", "Buy 5 AAPL")
    actions = [
        {"type": "trade", "status": "success", "ticker": "AAPL", "side": "buy", "quantity": 5}
    ]
    saved = append_chat_message("assistant", "Bought 5 AAPL at $190.", actions=actions)

    assert saved.role == "assistant"
    assert saved.actions == actions

    messages = get_chat_messages()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Buy 5 AAPL"
    assert messages[0].actions is None
    assert messages[1].role == "assistant"
    assert messages[1].actions == actions


def test_messages_are_chronological(db_path):
    for i in range(5):
        append_chat_message("user", f"message {i}")
    messages = get_chat_messages()
    assert [m.content for m in messages] == [f"message {i}" for i in range(5)]


def test_get_chat_messages_respects_limit(db_path):
    for i in range(60):
        append_chat_message("user", f"message {i}")
    messages = get_chat_messages(limit=50)
    assert len(messages) == 50
    # Most recent 50, still chronological.
    assert messages[0].content == "message 10"
    assert messages[-1].content == "message 59"


def test_null_actions_round_trip_as_none(db_path):
    saved = append_chat_message("user", "hello", actions=None)
    assert saved.actions is None
    fetched = get_chat_messages()[0]
    assert fetched.actions is None
