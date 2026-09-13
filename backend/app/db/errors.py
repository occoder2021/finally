"""Shared error type for the db, api, and llm layers.

Defined here (not in `app/api`) so `app/db` and `app/llm` can raise it
without importing the api layer, per TEAM_CONTRACT.md 4. `app/api` installs
one FastAPI exception handler that turns this into the error envelope:
`{"error": {"code": ..., "message": ...}}`.
"""

from __future__ import annotations


class ApiError(Exception):
    """A condition that should surface to the client as a structured error.

    `message` is written in plain English with concrete numbers -- it is
    shown to the user verbatim. `status` defaults to 400 because every code
    currently raised by this package is a validation failure; the parameter
    exists so a future 5xx-worthy condition doesn't need a second exception
    type.
    """

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def __repr__(self) -> str:
        return f"ApiError(code={self.code!r}, status={self.status}, message={self.message!r})"
