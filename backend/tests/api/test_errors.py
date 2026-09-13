"""The single error-envelope handler (TEAM_CONTRACT §4).

Uses a throwaway app with routes that deliberately raise each error kind,
independent of the portfolio/watchlist routers, so these tests pin the
envelope shape itself rather than any particular endpoint's business logic.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.errors import install_exception_handlers
from app.db import ApiError


class _ValidateBody(BaseModel):
    # Must live at module scope: a class defined inside the fixture function
    # defeats FastAPI's annotation resolution under `from __future__ import
    # annotations` (the string "Body" can't be found in the function's
    # globals), which silently reclassifies the body param as a query param.
    quantity: float


@pytest.fixture
def error_app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/boom/api-error")
    async def boom_api_error() -> dict:
        raise ApiError("INSUFFICIENT_CASH", "Need $1,900.00 but only $1,000.00 available.")

    @app.get("/boom/api-error-custom-status")
    async def boom_api_error_custom_status() -> dict:
        raise ApiError("SOMETHING", "custom status case", status=404)

    @app.get("/boom/unhandled")
    async def boom_unhandled() -> dict:
        raise RuntimeError("kaboom")

    @app.post("/boom/validate")
    async def boom_validate(body: _ValidateBody) -> dict:
        return {"quantity": body.quantity}

    return app


@pytest.fixture
def error_client(error_app: FastAPI) -> TestClient:
    return TestClient(error_app, raise_server_exceptions=False)


class TestApiErrorEnvelope:
    def test_api_error_renders_as_envelope_with_400(self, error_client: TestClient):
        resp = error_client.get("/boom/api-error")
        assert resp.status_code == 400
        assert resp.json() == {
            "error": {
                "code": "INSUFFICIENT_CASH",
                "message": "Need $1,900.00 but only $1,000.00 available.",
            }
        }

    def test_api_error_honors_custom_status(self, error_client: TestClient):
        resp = error_client.get("/boom/api-error-custom-status")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "SOMETHING"


class TestValidationErrorEnvelope:
    def test_missing_field_normalizes_to_400_envelope(self, error_client: TestClient):
        resp = error_client.post("/boom/validate", json={})
        assert resp.status_code == 400
        body = resp.json()
        assert set(body.keys()) == {"error"}
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "quantity" in body["error"]["message"]

    def test_wrong_type_normalizes_to_400_envelope(self, error_client: TestClient):
        resp = error_client.post("/boom/validate", json={"quantity": "not-a-number"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


class TestUnhandledErrorEnvelope:
    def test_unhandled_exception_renders_as_generic_500_envelope(self, error_client: TestClient):
        resp = error_client.get("/boom/unhandled")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        # The raw exception message must never leak to the client.
        assert "kaboom" not in body["error"]["message"]
