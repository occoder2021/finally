"""LLM_MOCK=true must be deterministic and still exercise the real
execution path — E2E tests depend on this."""

from app.llm.mock import mock_response
from app.llm.schema import WatchlistChangeRequest


class TestTradeParsing:
    def test_buy_produces_trade_action(self):
        resp = mock_response("buy 5 AAPL", cash_balance=1000.0, position_count=0)
        assert len(resp.trades) == 1
        t = resp.trades[0]
        assert (t.ticker, t.side, t.quantity) == ("AAPL", "buy", 5.0)

    def test_sell_produces_trade_action(self):
        resp = mock_response("please sell 2.5 NVDA now", cash_balance=1000.0, position_count=1)
        t = resp.trades[0]
        assert (t.ticker, t.side, t.quantity) == ("NVDA", "sell", 2.5)

    def test_case_insensitive(self):
        resp = mock_response("BUY 10 tsla", cash_balance=1000.0, position_count=0)
        assert resp.trades[0].ticker == "TSLA"
        assert resp.trades[0].side == "buy"

    def test_multiple_trades_in_one_message(self):
        resp = mock_response("buy 5 AAPL and buy 100 TSLA", cash_balance=1000.0, position_count=0)
        assert len(resp.trades) == 2

    def test_deterministic_across_calls(self):
        r1 = mock_response("buy 5 AAPL", cash_balance=1000.0, position_count=0)
        r2 = mock_response("buy 5 AAPL", cash_balance=1000.0, position_count=0)
        assert r1 == r2


class TestWatchlistParsing:
    def test_add_to_watchlist(self):
        resp = mock_response("add PYPL to watchlist", cash_balance=0.0, position_count=0)
        assert resp.watchlist_changes == [WatchlistChangeRequest(ticker="PYPL", action="add")]

    def test_add_to_the_watchlist_phrasing(self):
        resp = mock_response("add PYPL to the watchlist", cash_balance=0.0, position_count=0)
        assert len(resp.watchlist_changes) == 1
        assert resp.watchlist_changes[0].action == "add"

    def test_remove_from_watchlist(self):
        resp = mock_response("remove PYPL from watchlist", cash_balance=0.0, position_count=0)
        assert resp.watchlist_changes[0].action == "remove"
        assert resp.watchlist_changes[0].ticker == "PYPL"


class TestFallbackAnalysisReply:
    def test_unmatched_message_is_canned_analysis_with_no_actions(self):
        resp = mock_response("what do you think of my portfolio?", cash_balance=4321.0, position_count=3)
        assert resp.trades == []
        assert resp.watchlist_changes == []
        assert "4,321.00" in resp.message
        assert "3" in resp.message

    def test_fallback_is_deterministic_for_same_state(self):
        r1 = mock_response("analyze this", cash_balance=100.0, position_count=1)
        r2 = mock_response("analyze this", cash_balance=100.0, position_count=1)
        assert r1.message == r2.message
