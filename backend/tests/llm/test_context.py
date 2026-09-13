"""Portfolio context and message assembly for the prompt."""

from dataclasses import dataclass

from app.llm.context import SYSTEM_PROMPT, build_messages, format_portfolio_context
from tests.llm.conftest import FakeChatMessage, FakePosition, FakePriceCache


class TestFormatPortfolioContext:
    def test_empty_portfolio(self):
        ctx = format_portfolio_context(10000.0, [], [], FakePriceCache())
        assert "$10,000.00" in ctx
        assert "Positions: none" in ctx
        assert "Watchlist: none" in ctx

    def test_position_with_price_shows_pnl(self):
        positions = [FakePosition(ticker="AAPL", quantity=10, avg_cost=100.0)]
        cache = FakePriceCache({"AAPL": 110.0})
        ctx = format_portfolio_context(1000.0, positions, [], cache)
        assert "AAPL" in ctx
        assert "$100.00" in ctx  # avg cost
        assert "$110.00" in ctx  # current price
        assert "100.00" in ctx  # pnl = (110-100)*10 = 100.00

    def test_position_with_no_price_is_unavailable_not_zero(self):
        positions = [FakePosition(ticker="ZZZZ", quantity=5, avg_cost=50.0)]
        ctx = format_portfolio_context(1000.0, positions, [], FakePriceCache())
        assert "unavailable" in ctx
        assert "$0.00" not in ctx.split("unavailable")[0].split("ZZZZ")[-1][:50]

    def test_total_value_excludes_unpriced_positions_value(self):
        positions = [FakePosition(ticker="ZZZZ", quantity=100, avg_cost=50.0)]
        ctx = format_portfolio_context(1000.0, positions, [], FakePriceCache())
        assert "$1,000.00" in ctx  # cash-only total since ZZZZ has no price

    def test_watchlist_prices_rendered(self):
        cache = FakePriceCache({"NVDA": 480.5})
        ctx = format_portfolio_context(0.0, [], ["NVDA", "TSLA"], cache)
        assert "NVDA: $480.50" in ctx
        assert "TSLA: unavailable" in ctx


class TestBuildMessages:
    def test_includes_system_prompt_and_context(self):
        messages = build_messages("some context", [], "hi")
        assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
        assert "some context" in messages[1]["content"]

    def test_appends_user_message_last(self):
        messages = build_messages("ctx", [], "buy 5 AAPL")
        assert messages[-1] == {"role": "user", "content": "buy 5 AAPL"}

    def test_history_preserved_in_order(self):
        history = [
            FakeChatMessage(id="1", role="user", content="hi", actions=None, created_at="t1"),
            FakeChatMessage(id="2", role="assistant", content="hello", actions=None, created_at="t2"),
        ]
        messages = build_messages("ctx", history, "new message")
        roles_contents = [(m["role"], m["content"]) for m in messages]
        assert ("user", "hi") in roles_contents
        assert ("assistant", "hello") in roles_contents
        # history sits between the two system messages and the new user turn
        assert roles_contents.index(("user", "hi")) < roles_contents.index(("assistant", "hello"))
        assert messages[-1]["content"] == "new message"

    def test_unknown_role_is_coerced_to_user(self):
        @dataclass
        class Weird:
            role: str
            content: str

        messages = build_messages("ctx", [Weird(role="system", content="sneaky")], "hi")
        matching = [m for m in messages if m["content"] == "sneaky"]
        assert matching[0]["role"] == "user"
