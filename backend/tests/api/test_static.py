"""Static frontend export mounting: catch-all registered after /api/*, a
graceful skip when the build output doesn't exist (the normal case in dev),
and -- the regression this file exists to pin -- an *unmatched* `/api/*`
path must 404 as the standard JSON envelope, never fall through to
`index.html` with a 200. Mount ordering alone protects matched `/api/*`
routes; it does nothing for a path under `/api/` that no route claims."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.static import mount_static


def _api_health_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


class TestStaticDirectoryMissing:
    """The normal case in dev, before the frontend has been built."""

    def test_known_api_route_still_works(self, tmp_path):
        app = _api_health_app()
        mount_static(app, static_dir=str(tmp_path / "does-not-exist"))
        client = TestClient(app)

        assert client.get("/api/health").json() == {"status": "ok"}

    def test_unmatched_api_path_is_json_404_envelope(self, tmp_path):
        app = _api_health_app()
        mount_static(app, static_dir=str(tmp_path / "does-not-exist"))
        client = TestClient(app)

        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.json() == {
            "error": {
                "code": "NOT_FOUND",
                "message": "/api/nonexistent is not a valid API endpoint.",
            }
        }

    def test_unmatched_non_api_path_is_a_plain_404(self, tmp_path):
        """No frontend build to fall back to -- a plain 404, not HTML."""
        app = _api_health_app()
        mount_static(app, static_dir=str(tmp_path / "does-not-exist"))
        client = TestClient(app)

        assert client.get("/some/unknown/path").status_code == 404


class TestStaticDirectoryPresent:
    def _build_app(self, tmp_path):
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>home</html>", encoding="utf-8")
        (static_dir / "favicon.ico").write_bytes(b"ICO")

        app = _api_health_app()
        mount_static(app, static_dir=str(static_dir))
        return TestClient(app)

    def test_known_api_route_still_works(self, tmp_path):
        client = self._build_app(tmp_path)
        assert client.get("/api/health").json() == {"status": "ok"}

    def test_unmatched_api_path_is_json_404_not_index_html(self, tmp_path):
        """The exact regression from the container run: /api/nonexistent and
        /api/foo/bar/baz must never come back as index.html with a 200."""
        client = self._build_app(tmp_path)

        for path in ("/api/nonexistent", "/api/foo/bar/baz"):
            resp = client.get(path)
            assert resp.status_code == 404, path
            assert resp.headers["content-type"].startswith("application/json"), path
            body = resp.json()
            assert body["error"]["code"] == "NOT_FOUND"
            assert "html" not in resp.headers["content-type"]

    def test_real_static_asset_is_served(self, tmp_path):
        client = self._build_app(tmp_path)
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        assert resp.content == b"ICO"

    def test_unknown_non_api_path_falls_back_to_index_html(self, tmp_path):
        client = self._build_app(tmp_path)
        resp = client.get("/dashboard/whatever")
        assert resp.status_code == 200
        assert "home" in resp.text
