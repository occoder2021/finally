"""Executes a validated structured response's actions against the shared
trade/watchlist execution paths in `app.db`.

Manual trades and LLM trades must use the identical validation and
accounting path (PLAN.md §8, §14.2) — this module never re-implements
insufficient-cash / insufficient-shares / price checks itself. It resolves a
price from the price cache and delegates to the injected `execute_trade_fn`
(`app.db.execute_trade`), then reports whatever that call actually did.
Functions here are dependency-injected (no `import app.db`) so they're
testable with plain fakes independent of the db layer's build status.
"""

from __future__ import annotations

from typing import Any, Callable

from .schema import TradeRequest, WatchlistChangeRequest


def execute_trades(
    trades: list[TradeRequest],
    *,
    price_cache: Any,
    execute_trade_fn: Callable[..., Any],
    api_error_cls: type[Exception],
) -> list[dict]:
    """Run trades sequentially, best-effort. A later trade can legitimately
    fail because an earlier one consumed the cash — expected, not a bug —
    and each outcome is reported independently, never inferred from the
    model's `message`."""
    results: list[dict] = []
    for trade in trades:
        price = price_cache.get_price(trade.ticker)
        if price is None:
            results.append(
                {
                    "type": "trade",
                    "status": "failed",
                    "ticker": trade.ticker,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "detail": f"No current price available for {trade.ticker}.",
                }
            )
            continue
        try:
            result = execute_trade_fn(
                ticker=trade.ticker, side=trade.side, quantity=trade.quantity, price=price,
            )
        except api_error_cls as exc:
            results.append(
                {
                    "type": "trade",
                    "status": "failed",
                    "ticker": trade.ticker,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "detail": getattr(exc, "message", str(exc)),
                }
            )
            continue
        verb = "Bought" if trade.side == "buy" else "Sold"
        results.append(
            {
                "type": "trade",
                "status": "success",
                "ticker": result.ticker,
                "side": result.side,
                "quantity": result.quantity,
                "price": result.price,
                "total": result.total,
                "detail": f"{verb} {result.quantity:g} {result.ticker} at ${result.price:.2f}.",
            }
        )
    return results


async def execute_watchlist_changes(
    changes: list[WatchlistChangeRequest],
    *,
    add_fn: Callable[..., str],
    remove_fn: Callable[..., None],
    api_error_cls: type[Exception],
    get_tracked_tickers_fn: Callable[[], list[str]] | None = None,
    market_source: Any = None,
) -> list[dict]:
    """Run watchlist changes sequentially, best-effort, mirroring the manual
    `/api/watchlist` endpoints' tracked-set upkeep: adds start tracking
    immediately; removes only stop tracking if nothing still holds the
    ticker (a position must never silently lose its price).

    `market_source.add_ticker` / `remove_ticker` are async on the real
    `MarketDataSource` interface (`app/market/interface.py`), hence this
    function is async and awaits them — a synchronous call would silently
    no-op (the coroutine is created but never run).
    """
    results: list[dict] = []
    for change in changes:
        try:
            if change.action == "add":
                ticker = add_fn(ticker=change.ticker)
                if market_source is not None:
                    await market_source.add_ticker(ticker)
                results.append(
                    {
                        "type": "watchlist",
                        "status": "success",
                        "ticker": ticker,
                        "action": "add",
                        "detail": f"Added {ticker} to the watchlist.",
                    }
                )
            else:
                remove_fn(ticker=change.ticker)
                normalized = change.ticker.strip().upper()
                if market_source is not None and get_tracked_tickers_fn is not None:
                    if normalized not in get_tracked_tickers_fn():
                        await market_source.remove_ticker(normalized)
                results.append(
                    {
                        "type": "watchlist",
                        "status": "success",
                        "ticker": normalized,
                        "action": "remove",
                        "detail": f"Removed {normalized} from the watchlist.",
                    }
                )
        except api_error_cls as exc:
            results.append(
                {
                    "type": "watchlist",
                    "status": "failed",
                    "ticker": change.ticker,
                    "action": change.action,
                    "detail": getattr(exc, "message", str(exc)),
                }
            )
    return results
