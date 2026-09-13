"""Structured-output schema for the FinAlly chat assistant.

The model is instructed (via LiteLLM's `response_format`) to return JSON
matching `ChatStructuredResponse`. Nothing downstream — the executor, the
router — ever acts on unvalidated model output; this module is the single
gate everything sits behind, per PLAN.md §9 and TEAM_CONTRACT.md §7:
"Validate the complete structured response before executing anything."
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class TradeRequest(BaseModel):
    """One trade the model wants to execute. Mirrors the manual trade body
    (`{ticker, side, quantity}`) so both paths validate identically once this
    reaches `app.db.execute_trade`."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChangeRequest(BaseModel):
    """One watchlist modification the model wants to make."""

    ticker: str
    action: Literal["add", "remove"]


class ChatStructuredResponse(BaseModel):
    """The complete structured response requested from the model, per
    PLAN.md §9. `message` is always required; `trades` and
    `watchlist_changes` default to empty so a pure-conversation reply is a
    valid response with no forced action loop."""

    message: str
    trades: list[TradeRequest] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChangeRequest] = Field(default_factory=list)


class LLMCallError(Exception):
    """The provider call itself failed (network, provider error, timeout).

    Maps to the `LLM_ERROR` code at the router layer.
    """


class LLMValidationError(Exception):
    """The provider responded, but the content did not satisfy the schema —
    empty content, invalid JSON, or a schema mismatch.

    Maps to the `LLM_INVALID_RESPONSE` code at the router layer. No repair
    retry, no provider fallback — explicitly out of scope for v1.
    """


def parse_structured_response(raw_content: str | None) -> ChatStructuredResponse:
    """Parse and fully validate a raw model response before anything else
    touches it. Raises `LLMValidationError` on any failure to satisfy the
    schema, which the caller must treat as "execute zero actions"."""
    if not raw_content or not raw_content.strip():
        raise LLMValidationError("The AI returned an empty response.")
    try:
        return ChatStructuredResponse.model_validate_json(raw_content)
    except ValidationError as exc:
        raise LLMValidationError(
            f"The AI response did not match the expected format: {exc}"
        ) from exc
