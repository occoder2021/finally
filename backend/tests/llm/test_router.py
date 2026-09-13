"""`POST /api/chat` and `GET /api/chat/history`, wired to a fake `app.db`
(monkeypatched onto `app.llm.router._db`, since the real db layer is being
built in parallel — see tests/llm/conftest.py). A local exception handler
mirrors the envelope backend-api installs in the real app (TEAM_CONTRACT.md
§4) so these tests can assert on it without depending on `app.main`.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.llm.router import create_chat_router
from app.llm.schema import LLMCallError, LLMValidationError
from tests.llm.conftest import ApiError, FakeChatMessage, FakeDb, FakeMarketSource, FakePriceCache


def _client(db: FakeDb, price_cache: FakePriceCache | None = None, market_source=None) -> TestClient:
    app = FastAPI()
    app.include_router(create_chat_router(price_cache or FakePriceCache(), market_source))

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}},
        )

    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """Every test controls LLM_MOCK / OPENROUTER_API_KEY explicitly."""
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def _patch_db(monkeypatch, db: FakeDb) -> None:
    import app.llm.router as router_module

    monkeypatch.setattr(router_module, "_db", lambda: db)


class TestChatUnavailable:
    def test_no_key_and_not_mock_returns_chat_unavailable(self, monkeypatch):
        db = FakeDb()
        _patch_db(monkeypatch, db)
        resp = _client(db).post("/api/chat", json={"message": "hi"})

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "CHAT_UNAVAILABLE"
        # Nothing should be persisted for a request that never ran.
        assert db.appended_messages == []

    def test_mock_true_bypasses_missing_key(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        db = FakeDb()
        _patch_db(monkeypatch, db)
        resp = _client(db).post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 200


class TestMockModeExecution:
    def test_buy_message_executes_real_trade_path(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        db = FakeDb(cash_balance=10000.0)
        cache = FakePriceCache({"NVDA": 480.0})
        _patch_db(monkeypatch, db)

        resp = _client(db, cache).post("/api/chat", json={"message": "buy 5 NVDA"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["actions"][0]["status"] == "success"
        assert body["actions"][0]["ticker"] == "NVDA"
        assert db.executed_trades == [("NVDA", "buy", 5.0, 480.0)]

    def test_analysis_message_executes_nothing(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        db = FakeDb()
        _patch_db(monkeypatch, db)

        resp = _client(db).post("/api/chat", json={"message": "how am I doing?"})

        assert resp.status_code == 200
        assert resp.json()["actions"] == []
        assert db.executed_trades == []

    def test_watchlist_add_message_syncs_market_source(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        db = FakeDb()
        market_source = FakeMarketSource()
        _patch_db(monkeypatch, db)

        resp = _client(db, market_source=market_source).post(
            "/api/chat", json={"message": "add PYPL to watchlist"},
        )

        assert resp.status_code == 200
        assert resp.json()["actions"][0]["status"] == "success"
        assert market_source.added == ["PYPL"]

    def test_persists_user_and_assistant_messages_with_actions(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        db = FakeDb()
        cache = FakePriceCache({"AAPL": 100.0})
        _patch_db(monkeypatch, db)

        _client(db, cache).post("/api/chat", json={"message": "buy 1 AAPL"})

        assert len(db.appended_messages) == 2
        assert db.appended_messages[0].role == "user"
        assert db.appended_messages[0].content == "buy 1 AAPL"
        assert db.appended_messages[0].actions is None
        assert db.appended_messages[1].role == "assistant"
        assert db.appended_messages[1].actions[0]["status"] == "success"


class TestBestEffortSequencing:
    def test_second_trade_fails_after_first_spends_cash(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        db = FakeDb(
            cash_balance=1000.0,
            trade_side_effects=[None, ApiError("INSUFFICIENT_CASH", "Not enough cash.")],
        )
        cache = FakePriceCache({"AAPL": 100.0, "TSLA": 900.0})
        _patch_db(monkeypatch, db)

        resp = _client(db, cache).post(
            "/api/chat", json={"message": "buy 1 AAPL and buy 100 TSLA"},
        )

        actions = resp.json()["actions"]
        assert actions[0]["status"] == "success"
        assert actions[1]["status"] == "failed"
        assert actions[1]["detail"] == "Not enough cash."
        # The model's message is never treated as proof of execution — the
        # caller must read outcomes from `actions`, not from `message`.
        assert resp.status_code == 200


class TestRealLlmPath:
    def test_valid_response_executes_and_persists(self, monkeypatch):
        db = FakeDb()
        cache = FakePriceCache({"AAPL": 100.0})
        _patch_db(monkeypatch, db)
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

        import app.llm.router as router_module
        from app.llm.schema import ChatStructuredResponse, TradeRequest

        monkeypatch.setattr(
            router_module,
            "call_llm",
            lambda messages: ChatStructuredResponse(
                message="Bought it.", trades=[TradeRequest(ticker="AAPL", side="buy", quantity=1)],
            ),
        )

        resp = _client(db, cache).post("/api/chat", json={"message": "buy 1 AAPL"})

        assert resp.status_code == 200
        assert resp.json()["actions"][0]["status"] == "success"
        assert len(db.appended_messages) == 2

    def test_call_error_returns_llm_error_and_persists_nothing(self, monkeypatch):
        db = FakeDb()
        _patch_db(monkeypatch, db)
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

        import app.llm.router as router_module

        def _raise(messages):
            raise LLMCallError("provider down")

        monkeypatch.setattr(router_module, "call_llm", _raise)

        resp = _client(db).post("/api/chat", json={"message": "hi"})

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "LLM_ERROR"
        assert db.appended_messages == []

    def test_invalid_schema_response_returns_llm_invalid_response_and_executes_nothing(self, monkeypatch):
        db = FakeDb()
        _patch_db(monkeypatch, db)
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

        import app.llm.router as router_module

        def _raise(messages):
            raise LLMValidationError("bad json")

        monkeypatch.setattr(router_module, "call_llm", _raise)

        resp = _client(db).post("/api/chat", json={"message": "hi"})

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "LLM_INVALID_RESPONSE"
        assert db.appended_messages == []
        assert db.executed_trades == []


class TestContextBounds:
    def test_context_history_bounded_to_20(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        history = [
            FakeChatMessage(id=str(i), role="user", content=f"msg{i}", actions=None, created_at=f"t{i}")
            for i in range(30)
        ]
        db = FakeDb(chat_messages=history)
        _patch_db(monkeypatch, db)

        _client(db).post("/api/chat", json={"message": "hi"})

        assert db.get_chat_messages_calls[0] == 20


class TestChatHistoryEndpoint:
    def test_returns_up_to_50_chronological(self, monkeypatch):
        history = [
            FakeChatMessage(id=str(i), role="user", content=f"msg{i}", actions=None, created_at=f"t{i}")
            for i in range(5)
        ]
        db = FakeDb(chat_messages=history)
        _patch_db(monkeypatch, db)

        resp = _client(db).get("/api/chat/history")

        assert resp.status_code == 200
        body = resp.json()
        assert [m["content"] for m in body["messages"]] == [f"msg{i}" for i in range(5)]
        assert db.get_chat_messages_calls[-1] == 50

    def test_includes_recorded_action_outcomes(self, monkeypatch):
        history = [
            FakeChatMessage(
                id="1", role="assistant", content="Bought it.",
                actions=[{"type": "trade", "status": "success", "ticker": "AAPL"}],
                created_at="t1",
            ),
        ]
        db = FakeDb(chat_messages=history)
        _patch_db(monkeypatch, db)

        resp = _client(db).get("/api/chat/history")

        assert resp.json()["messages"][0]["actions"] == [
            {"type": "trade", "status": "success", "ticker": "AAPL"}
        ]
