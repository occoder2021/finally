"""The chat router: `POST /api/chat` and `GET /api/chat/history`.

Owned exclusively by the llm-engineer per TEAM_CONTRACT.md §7. `main.py`
(owned by backend-api) mounts `create_chat_router(price_cache, market_source)`
— this module never touches `main.py` itself.

`app.db` is imported lazily, inside `_db()`, rather than at module import
time. The db layer is being built in parallel per TEAM_CONTRACT.md's shared
build, so this keeps `app.llm` importable — and its non-db pieces testable —
independent of build order. By integration time `app.db` is expected to
exist and this is just an ordinary call.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from .client import call_llm
from .context import build_messages, format_portfolio_context
from .executor import execute_trades, execute_watchlist_changes
from .mock import mock_response
from .schema import LLMCallError, LLMValidationError

logger = logging.getLogger(__name__)

# Context sent to the model is bounded to the last 20 messages (PLAN.md §9);
# the history endpoint itself returns up to the last 50 (PLAN.md §8).
HISTORY_LIMIT_FOR_CONTEXT = 20
HISTORY_LIMIT_FOR_ENDPOINT = 50


class ChatRequest(BaseModel):
    message: str


def _db() -> Any:
    """Import `app.db` lazily so build order between agents doesn't matter."""
    import app.db as db

    return db


def _mock_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def _chat_unavailable() -> bool:
    """True when chat cannot run: no API key configured and mock mode is not
    explicitly enabled. Mock mode is entered ONLY via `LLM_MOCK=true` —
    never as a silent fallback when the key is simply missing."""
    if _mock_enabled():
        return False
    return not os.environ.get("OPENROUTER_API_KEY", "").strip()


def create_chat_router(price_cache: Any, market_source: Any | None = None) -> APIRouter:
    """Create the chat router bound to the shared price cache and (optionally)
    the market data source, so LLM-initiated watchlist changes keep the
    tracked ticker set in sync exactly like the manual `/api/watchlist`
    endpoints do."""
    router = APIRouter(tags=["chat"])

    @router.post("/api/chat")
    async def post_chat(payload: ChatRequest) -> dict:
        db = _db()

        if _chat_unavailable():
            raise db.ApiError(
                "CHAT_UNAVAILABLE",
                "Chat is unavailable because no OpenRouter API key is configured.",
            )

        cash_balance = db.get_cash_balance()
        positions = db.get_positions()
        watchlist = db.get_watchlist()
        portfolio_context = format_portfolio_context(cash_balance, positions, watchlist, price_cache)

        history = db.get_chat_messages(limit=HISTORY_LIMIT_FOR_CONTEXT)
        messages = build_messages(portfolio_context, history, payload.message)

        if _mock_enabled():
            structured = mock_response(
                payload.message, cash_balance=cash_balance, position_count=len(positions),
            )
        else:
            try:
                structured = call_llm(messages)
            except LLMCallError as exc:
                raise db.ApiError("LLM_ERROR", str(exc)) from exc
            except LLMValidationError as exc:
                raise db.ApiError("LLM_INVALID_RESPONSE", str(exc)) from exc

        # Only persisted once we have a validated response to act on — a
        # failed call/validation above raises before anything is written, so
        # the conversation history never gets an orphaned user turn.
        db.append_chat_message(role="user", content=payload.message, actions=None)

        actions = execute_trades(
            structured.trades,
            price_cache=price_cache,
            execute_trade_fn=db.execute_trade,
            api_error_cls=db.ApiError,
        )
        actions += await execute_watchlist_changes(
            structured.watchlist_changes,
            add_fn=db.add_to_watchlist,
            remove_fn=db.remove_from_watchlist,
            api_error_cls=db.ApiError,
            get_tracked_tickers_fn=db.get_tracked_tickers,
            market_source=market_source,
        )

        db.append_chat_message(role="assistant", content=structured.message, actions=actions or None)

        return {"message": structured.message, "actions": actions}

    @router.get("/api/chat/history")
    async def get_chat_history() -> dict:
        db = _db()
        messages = db.get_chat_messages(limit=HISTORY_LIMIT_FOR_ENDPOINT)
        return {
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "actions": m.actions,
                    "created_at": m.created_at,
                }
                for m in messages
            ]
        }

    return router
