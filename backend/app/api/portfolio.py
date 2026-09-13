"""Portfolio endpoints: holdings valuation, trade execution, value history.

TEAM_CONTRACT §6. `POST /api/portfolio/trade` is the only place a manual trade
is validated and executed, and it does so purely by resolving a price from the
shared `price_cache` and delegating to `app.db.execute_trade` — the single
execution path shared with the LLM chat flow. No trade validation or
accounting logic lives here.
"""

from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter, Depends

from app.market import MarketDataSource, PriceCache

from .deps import get_db_module
from .schemas import TradeRequest

# Matches the fixed seed cash balance (PLAN.md §7). Not stored per-user
# because this is a single-user simulator with no reset flow yet.
STARTING_CASH = 10000.0


def create_portfolio_router(
    price_cache: PriceCache,
    market_source: MarketDataSource,
) -> APIRouter:
    """Build the portfolio router bound to the shared price cache and market source."""
    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

    @router.get("")
    async def get_portfolio(db: ModuleType = Depends(get_db_module)) -> dict:
        cash_balance = db.get_cash_balance()
        positions_out = []
        total_value = cash_balance
        total_unrealized_pnl = 0.0

        for pos in db.get_positions():
            price = price_cache.get_price(pos.ticker)
            if price is None:
                # Never valued at zero, never dropped — just marked unavailable.
                positions_out.append(
                    {
                        "ticker": pos.ticker,
                        "quantity": pos.quantity,
                        "avg_cost": pos.avg_cost,
                        "current_price": None,
                        "market_value": None,
                        "unrealized_pnl": None,
                        "pnl_percent": None,
                        "price_available": False,
                    }
                )
                continue

            market_value = price * pos.quantity
            cost_basis = pos.avg_cost * pos.quantity
            unrealized_pnl = market_value - cost_basis
            pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0

            positions_out.append(
                {
                    "ticker": pos.ticker,
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                    "current_price": price,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized_pnl,
                    "pnl_percent": pnl_percent,
                    "price_available": True,
                }
            )
            total_value += market_value
            total_unrealized_pnl += unrealized_pnl

        return {
            "cash_balance": cash_balance,
            "positions": positions_out,
            "total_value": total_value,
            "total_unrealized_pnl": total_unrealized_pnl,
            "starting_cash": STARTING_CASH,
        }

    @router.post("/trade", status_code=200)
    async def post_trade(
        body: TradeRequest, db: ModuleType = Depends(get_db_module)
    ) -> dict:
        ticker = body.ticker.strip().upper()
        price = price_cache.get_price(ticker)
        if price is None:
            raise db.ApiError(
                code="PRICE_UNAVAILABLE",
                message=f"No current price is available for {ticker}.",
                status=400,
            )

        result = db.execute_trade(
            ticker=ticker, side=body.side, quantity=body.quantity, price=price
        )

        # Keep the trade log's ticker tracked for pricing even if it's not on
        # the watchlist (e.g. a bare LLM-directed trade in an unwatched name).
        await market_source.add_ticker(result.ticker)

        db.record_snapshot(total_value=value_portfolio(db, price_cache))

        return {
            "trade": {
                "ticker": result.ticker,
                "side": result.side,
                "quantity": result.quantity,
                "price": result.price,
                "total": result.total,
                "executed_at": result.executed_at,
                "cash_after": result.cash_after,
            }
        }

    @router.get("/history")
    async def get_history(db: ModuleType = Depends(get_db_module)) -> dict:
        return {"snapshots": db.get_snapshots(limit=500)}

    return router


def value_portfolio(db: ModuleType, price_cache: PriceCache) -> float:
    """Total portfolio value from db holdings + live cached prices.

    Shared by the trade route's post-trade snapshot and the 30s background
    snapshot task so the two writers can never disagree on the formula.
    Positions with no cached price contribute 0, same rule as `GET /api/portfolio`.
    """
    total = db.get_cash_balance()
    for pos in db.get_positions():
        price = price_cache.get_price(pos.ticker)
        if price is not None:
            total += price * pos.quantity
    return total
