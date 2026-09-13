"""Request bodies for the API layer.

Field-level shape validation only (types, required-ness). Business validation
— quantity sign/finiteness, cash/share sufficiency, ticker format — belongs to
`app.db` (see TEAM_CONTRACT §5) and is never duplicated here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    quantity: float
    side: Literal["buy", "sell"]


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
