"""Structured-output parsing/validation: the single gate everything else
sits behind. Malformed input must never reach the executor."""

import pytest

from app.llm.schema import (
    ChatStructuredResponse,
    LLMValidationError,
    TradeRequest,
    WatchlistChangeRequest,
    parse_structured_response,
)


class TestValidShapes:
    def test_message_only(self):
        resp = parse_structured_response('{"message": "Hello there."}')
        assert resp.message == "Hello there."
        assert resp.trades == []
        assert resp.watchlist_changes == []

    def test_trades_only(self):
        raw = '{"message": "Buying.", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}'
        resp = parse_structured_response(raw)
        assert resp.trades == [TradeRequest(ticker="AAPL", side="buy", quantity=5)]
        assert resp.watchlist_changes == []

    def test_watchlist_only(self):
        raw = '{"message": "Tracking.", "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]}'
        resp = parse_structured_response(raw)
        assert resp.watchlist_changes == [WatchlistChangeRequest(ticker="PYPL", action="add")]
        assert resp.trades == []

    def test_trades_and_watchlist(self):
        raw = (
            '{"message": "Doing both.", '
            '"trades": [{"ticker": "NVDA", "side": "sell", "quantity": 2.5}], '
            '"watchlist_changes": [{"ticker": "TSLA", "action": "remove"}]}'
        )
        resp = parse_structured_response(raw)
        assert len(resp.trades) == 1
        assert len(resp.watchlist_changes) == 1
        assert isinstance(resp, ChatStructuredResponse)


class TestMalformedInput:
    def test_none_content_raises(self):
        with pytest.raises(LLMValidationError):
            parse_structured_response(None)

    def test_empty_string_raises(self):
        with pytest.raises(LLMValidationError):
            parse_structured_response("")

    def test_whitespace_only_raises(self):
        with pytest.raises(LLMValidationError):
            parse_structured_response("   \n  ")

    def test_invalid_json_raises(self):
        with pytest.raises(LLMValidationError):
            parse_structured_response("not json at all")

    def test_missing_required_field_raises(self):
        with pytest.raises(LLMValidationError):
            parse_structured_response('{"trades": []}')

    def test_wrong_type_raises(self):
        with pytest.raises(LLMValidationError):
            parse_structured_response('{"message": 123}')

    def test_invalid_side_raises(self):
        raw = '{"message": "x", "trades": [{"ticker": "AAPL", "side": "hold", "quantity": 1}]}'
        with pytest.raises(LLMValidationError):
            parse_structured_response(raw)

    def test_invalid_watchlist_action_raises(self):
        raw = '{"message": "x", "watchlist_changes": [{"ticker": "AAPL", "action": "delete"}]}'
        with pytest.raises(LLMValidationError):
            parse_structured_response(raw)

    def test_extra_top_level_junk_is_not_valid_json_object_for_schema(self):
        # A JSON array instead of an object should fail to validate.
        with pytest.raises(LLMValidationError):
            parse_structured_response("[1, 2, 3]")
