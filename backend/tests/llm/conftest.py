"""Fakes standing in for `app.db` and `app.market`, per TEAM_CONTRACT.md §5.

`app.db` does not exist yet (it's being built in parallel), and none of
`app.llm`'s modules import it at module load time — `router.py` resolves it
lazily via `_db()`. These fakes implement exactly the documented public API
signatures so tests exercise the real router/executor code paths without
depending on build order.
"""

from __future__ import annotations

from dataclasses import dataclass


class ApiError(Exception):
    """Stand-in for `app.db.errors.ApiError` — same shape: code, message,
    status, per TEAM_CONTRACT.md §4."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class FakePosition:
    ticker: str
    quantity: float
    avg_cost: float


@dataclass
class FakeTradeResult:
    ticker: str
    side: str
    quantity: float
    price: float
    total: float
    cash_after: float
    trade_id: str
    executed_at: str


@dataclass
class FakeChatMessage:
    id: str
    role: str
    content: str
    actions: list | None
    created_at: str


class FakeDb:
    """In-memory fake of the `app.db` public API (TEAM_CONTRACT.md §5),
    covering only what `app.llm` calls."""

    ApiError = ApiError

    def __init__(
        self,
        cash_balance: float = 10000.0,
        positions: list[FakePosition] | None = None,
        watchlist: list[str] | None = None,
        chat_messages: list[FakeChatMessage] | None = None,
        trade_side_effects: list | None = None,
    ) -> None:
        self._cash_balance = cash_balance
        self._positions = positions or []
        self._watchlist = watchlist or []
        self._chat_messages: list[FakeChatMessage] = list(chat_messages or [])
        # Queue of per-call overrides for execute_trade: an Exception is
        # raised, anything else is returned as-is instead of the default fill.
        self._trade_queue = list(trade_side_effects or [])

        self.executed_trades: list[tuple] = []
        self.appended_messages: list[FakeChatMessage] = []
        self.get_chat_messages_calls: list[int] = []

    def get_cash_balance(self, user_id: str = "default") -> float:
        return self._cash_balance

    def get_positions(self, user_id: str = "default") -> list[FakePosition]:
        return list(self._positions)

    def get_watchlist(self, user_id: str = "default") -> list[str]:
        return list(self._watchlist)

    def get_tracked_tickers(self, user_id: str = "default") -> list[str]:
        # Computed fresh each call, like the real db-layer union of watchlist
        # and non-zero positions — never a separately mutated set, so a
        # position always keeps its ticker tracked regardless of watchlist
        # membership.
        return sorted({p.ticker for p in self._positions} | set(self._watchlist))

    def get_chat_messages(self, limit: int = 50, user_id: str = "default") -> list[FakeChatMessage]:
        self.get_chat_messages_calls.append(limit)
        return list(self._chat_messages[-limit:])

    def append_chat_message(
        self, role: str, content: str, actions: list[dict] | None = None, user_id: str = "default",
    ) -> FakeChatMessage:
        msg = FakeChatMessage(
            id=f"m{len(self.appended_messages)}",
            role=role,
            content=content,
            actions=actions,
            created_at="2026-01-01T00:00:00",
        )
        self.appended_messages.append(msg)
        self._chat_messages.append(msg)
        return msg

    def execute_trade(
        self, ticker: str, side: str, quantity: float, price: float, user_id: str = "default",
    ) -> FakeTradeResult:
        self.executed_trades.append((ticker, side, quantity, price))
        if self._trade_queue:
            effect = self._trade_queue.pop(0)
            if isinstance(effect, Exception):
                raise effect
            if effect is not None:
                return effect
        total = round(quantity * price, 2)
        self._cash_balance = round(
            self._cash_balance - total if side == "buy" else self._cash_balance + total, 2,
        )
        return FakeTradeResult(
            ticker=ticker, side=side, quantity=quantity, price=price, total=total,
            cash_after=self._cash_balance, trade_id="t1", executed_at="2026-01-01T00:00:00",
        )

    def add_to_watchlist(self, ticker: str, user_id: str = "default") -> str:
        normalized = ticker.strip().upper()
        if normalized in self._watchlist:
            raise ApiError("DUPLICATE_TICKER", f"'{normalized}' is already on the watchlist.")
        self._watchlist.append(normalized)
        return normalized

    def remove_from_watchlist(self, ticker: str, user_id: str = "default") -> None:
        normalized = ticker.strip().upper()
        if normalized not in self._watchlist:
            raise ApiError("TICKER_NOT_FOUND", f"'{normalized}' is not on the watchlist.")
        self._watchlist.remove(normalized)


class FakePriceCache:
    """Stand-in for `app.market.PriceCache` — only `get_price` is used by
    `app.llm`."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices = dict(prices or {})

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)


class FakeMarketSource:
    """Records tracked-set upkeep calls without a real background feed.

    `add_ticker` / `remove_ticker` are `async def` to match the real
    `MarketDataSource` interface (`app/market/interface.py`) — a sync fake
    would let an `await`-less caller bug pass tests unnoticed.
    """

    def __init__(self) -> None:
        self.added: list[str] = []
        self.removed: list[str] = []

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)
