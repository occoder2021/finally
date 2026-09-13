"""The single error-envelope exception handler (TEAM_CONTRACT §4).

Every 4xx/5xx returned by `/api/*` renders as exactly:

    {"error": {"code": "INSUFFICIENT_CASH", "message": "..."}}

`ApiError` (raised by `app.db` and `app.llm`) carries its own `code`,
`message` and `status`; FastAPI's own request-validation errors (422) and any
other uncaught exception are normalized into the same shape here so the
frontend only ever has to parse one error format.

`ApiError` is registered as its own handler (not folded into the catch-all
`Exception` handler below) because Starlette dispatches a bare-`Exception`
handler through `ServerErrorMiddleware`, which builds the response and then
*re-raises* the exception so it's logged as an unhandled server error. An
`ApiError` -- a duplicate ticker, insufficient cash -- is an ordinary,
expected 400, not a bug; registering the concrete class routes it through
`ExceptionMiddleware` instead, which returns the response without re-raising
and without the spurious "unhandled exception" log noise on every validation
failure.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db import ApiError

logger = logging.getLogger(__name__)


def install_exception_handlers(app: FastAPI) -> None:
    """Register the error-envelope handlers on `app`. Call once, at app creation."""

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        if errors:
            first = errors[0]
            # loc[0] is "body"/"query"/"path"; the rest is the field path.
            field = ".".join(str(part) for part in first["loc"][1:])
            message = f"{field}: {first['msg']}" if field else first["msg"]
        else:
            message = "The request body is invalid."
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "VALIDATION_ERROR", "message": message}},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error in %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again.",
                }
            },
        )
