"""Sequential, best-effort execution of validated trades and watchlist
changes against the shared (fake) `app.db` execution path."""

from app.llm.executor import execute_trades, execute_watchlist_changes
from app.llm.schema import TradeRequest, WatchlistChangeRequest
from tests.llm.conftest import ApiError, FakeDb, FakeMarketSource, FakePriceCache


class TestExecuteTrades:
    def test_successful_trade_reports_fill_details(self):
        db = FakeDb()
        cache = FakePriceCache({"AAPL": 190.0})
        trades = [TradeRequest(ticker="AAPL", side="buy", quantity=5)]

        actions = execute_trades(
            trades, price_cache=cache, execute_trade_fn=db.execute_trade, api_error_cls=ApiError,
        )

        assert actions == [
            {
                "type": "trade", "status": "success", "ticker": "AAPL", "side": "buy",
                "quantity": 5, "price": 190.0, "total": 950.0,
                "detail": "Bought 5 AAPL at $190.00.",
            }
        ]
        assert db.executed_trades == [("AAPL", "buy", 5, 190.0)]

    def test_missing_price_fails_without_calling_execute_trade(self):
        db = FakeDb()
        cache = FakePriceCache({})  # no price for AAPL
        trades = [TradeRequest(ticker="AAPL", side="buy", quantity=5)]

        actions = execute_trades(
            trades, price_cache=cache, execute_trade_fn=db.execute_trade, api_error_cls=ApiError,
        )

        assert actions[0]["status"] == "failed"
        assert "AAPL" in actions[0]["detail"]
        assert db.executed_trades == []

    def test_second_trade_fails_after_first_spends_cash(self):
        """The canonical best-effort scenario: trade 1 succeeds and consumes
        cash, trade 2 legitimately fails on insufficient cash."""
        db = FakeDb(
            cash_balance=1000.0,
            trade_side_effects=[None, ApiError("INSUFFICIENT_CASH", "Need $24,000.00 but only $50.00 available.")],
        )
        cache = FakePriceCache({"AAPL": 190.0, "TSLA": 240.0})
        trades = [
            TradeRequest(ticker="AAPL", side="buy", quantity=5),
            TradeRequest(ticker="TSLA", side="buy", quantity=100),
        ]

        actions = execute_trades(
            trades, price_cache=cache, execute_trade_fn=db.execute_trade, api_error_cls=ApiError,
        )

        assert actions[0]["status"] == "success"
        assert actions[1]["status"] == "failed"
        assert actions[1]["detail"] == "Need $24,000.00 but only $50.00 available."
        assert "price" not in actions[1]
        # Both were attempted — the second's failure doesn't stop iteration early.
        assert len(db.executed_trades) == 2

    def test_invalid_quantity_error_is_reported_not_raised(self):
        db = FakeDb(trade_side_effects=[ApiError("INVALID_QUANTITY", "Quantity must be positive.")])
        cache = FakePriceCache({"AAPL": 190.0})
        trades = [TradeRequest(ticker="AAPL", side="buy", quantity=1)]

        actions = execute_trades(
            trades, price_cache=cache, execute_trade_fn=db.execute_trade, api_error_cls=ApiError,
        )

        assert actions[0]["status"] == "failed"
        assert actions[0]["detail"] == "Quantity must be positive."

    def test_empty_trades_returns_empty(self):
        db = FakeDb()
        actions = execute_trades(
            [], price_cache=FakePriceCache(), execute_trade_fn=db.execute_trade, api_error_cls=ApiError,
        )
        assert actions == []


class TestExecuteWatchlistChanges:
    async def test_successful_add_starts_tracking(self):
        db = FakeDb()
        market_source = FakeMarketSource()
        changes = [WatchlistChangeRequest(ticker="pypl", action="add")]

        actions = await execute_watchlist_changes(
            changes, add_fn=db.add_to_watchlist, remove_fn=db.remove_from_watchlist,
            api_error_cls=ApiError, get_tracked_tickers_fn=db.get_tracked_tickers,
            market_source=market_source,
        )

        assert actions == [
            {"type": "watchlist", "status": "success", "ticker": "PYPL", "action": "add",
             "detail": "Added PYPL to the watchlist."}
        ]
        assert market_source.added == ["PYPL"]

    async def test_duplicate_add_fails(self):
        db = FakeDb(watchlist=["AAPL"])
        changes = [WatchlistChangeRequest(ticker="AAPL", action="add")]

        actions = await execute_watchlist_changes(
            changes, add_fn=db.add_to_watchlist, remove_fn=db.remove_from_watchlist,
            api_error_cls=ApiError,
        )

        assert actions[0]["status"] == "failed"
        assert actions[0]["ticker"] == "AAPL"
        assert actions[0]["action"] == "add"

    async def test_remove_stops_tracking_when_no_open_position(self):
        db = FakeDb(watchlist=["PYPL"])
        market_source = FakeMarketSource()
        changes = [WatchlistChangeRequest(ticker="pypl", action="remove")]

        actions = await execute_watchlist_changes(
            changes, add_fn=db.add_to_watchlist, remove_fn=db.remove_from_watchlist,
            api_error_cls=ApiError, get_tracked_tickers_fn=db.get_tracked_tickers,
            market_source=market_source,
        )

        assert actions[0]["status"] == "success"
        assert market_source.removed == ["PYPL"]

    async def test_remove_keeps_tracking_when_position_still_open(self):
        """A held position must never silently lose its price, even after
        its ticker leaves the watchlist."""
        from tests.llm.conftest import FakePosition

        db = FakeDb(watchlist=["PYPL"], positions=[FakePosition(ticker="PYPL", quantity=3, avg_cost=10.0)])
        market_source = FakeMarketSource()
        changes = [WatchlistChangeRequest(ticker="PYPL", action="remove")]

        await execute_watchlist_changes(
            changes, add_fn=db.add_to_watchlist, remove_fn=db.remove_from_watchlist,
            api_error_cls=ApiError, get_tracked_tickers_fn=db.get_tracked_tickers,
            market_source=market_source,
        )

        assert market_source.removed == []

    async def test_remove_nonexistent_ticker_fails(self):
        db = FakeDb()
        changes = [WatchlistChangeRequest(ticker="ZZZZ", action="remove")]

        actions = await execute_watchlist_changes(
            changes, add_fn=db.add_to_watchlist, remove_fn=db.remove_from_watchlist,
            api_error_cls=ApiError,
        )

        assert actions[0]["status"] == "failed"

    async def test_mixed_success_and_failure_both_reported(self):
        db = FakeDb(watchlist=["AAPL"])
        changes = [
            WatchlistChangeRequest(ticker="AAPL", action="add"),  # duplicate -> fails
            WatchlistChangeRequest(ticker="PYPL", action="add"),  # succeeds
        ]

        actions = await execute_watchlist_changes(
            changes, add_fn=db.add_to_watchlist, remove_fn=db.remove_from_watchlist,
            api_error_cls=ApiError,
        )

        assert [a["status"] for a in actions] == ["failed", "success"]
