"""Serves the Next.js static export.

Registered as a catch-all, so it must be mounted *after* every `/api/*`
route (FastAPI matches routes in registration order) — otherwise it would
swallow API requests as "unknown paths" and return index.html for them.
Mount ordering alone only protects *matched* `/api/*` routes, though: an
*unmatched* one (a typo, a since-renamed endpoint) still falls through to
this catch-all, so the handler itself also checks the path prefix and
returns the standard JSON error envelope for anything under `/api/` instead
of silently handing back `index.html` with a 200. Skips gracefully when the
static directory doesn't exist (normal during development, before the
frontend has been built).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

DEFAULT_STATIC_DIR = "static"


def _api_not_found(full_path: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": f"/{full_path} is not a valid API endpoint.",
            }
        },
    )


def mount_static(app: FastAPI, static_dir: str | None = None) -> None:
    """Mount the static export directory on `app`, if it exists.

    `static_dir` defaults to the `FINALLY_STATIC_DIR` env var, falling back
    to `static/` relative to the backend working directory.
    """
    directory = Path(static_dir or os.environ.get("FINALLY_STATIC_DIR", DEFAULT_STATIC_DIR))

    if not directory.is_dir():
        logger.info("Static directory %s not found; skipping static file serving", directory)

        # Even without a build to serve, an unmatched /api/* path must still
        # 404 as JSON rather than fall through to Starlette's default HTML
        # 404 page -- the frontend's fetch layer only ever expects JSON from
        # anything under /api/.
        @app.get("/api/{full_path:path}", include_in_schema=False, response_model=None)
        async def api_not_found_no_static(full_path: str) -> JSONResponse:
            return _api_not_found(f"api/{full_path}")

        return

    # Serve hashed build assets (e.g. Next.js's _next/) directly.
    assets_dir = directory / "_next"
    if assets_dir.is_dir():
        app.mount("/_next", StaticFiles(directory=assets_dir), name="next-assets")

    index_file = directory / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def serve_frontend(full_path: str) -> Response:
        """Serve a static file if it exists at that path; JSON-404 an
        unmatched `/api/*` path; else fall back to index.html so
        client-side routing works for unknown non-API paths."""
        if full_path.startswith("api/") or full_path == "api":
            return _api_not_found(full_path)

        candidate = directory / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)

    logger.info("Serving static frontend from %s", directory)
