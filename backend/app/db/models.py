"""Return-type dataclasses for the db package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    """One holding: a ticker, its quantity, and its cost basis."""

    ticker: str
    quantity: float
    avg_cost: float


@dataclass(frozen=True, slots=True)
class TradeResult:
    """The outcome of a successfully executed trade."""

    ticker: str
    side: str
    quantity: float
    price: float
    total: float
    cash_after: float
    trade_id: str
    executed_at: str


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One row of conversation history, with its recorded action outcomes."""

    id: str
    role: str
    content: str
    actions: list[dict] | None
    created_at: str
