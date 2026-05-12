"""The one and only Python ↔ React seam.

The dashboard lives in `web_ui/` — a fully isolated Vite project that
builds to `web_ui/dist/`. This module mounts that build output as static
files served by the same FastAPI process, so a browser hitting `/` gets
the SPA while `/api/...` keeps serving JSON.

Removing the UI ("cheche") is exactly:
  1. `rm -rf web_ui/`
  2. Comment out the `mount_web_ui(app)` call in `main.py`
The JSON API and every cron CLI keep working.

Detail: SPA routes are client-side (`/inbox`, `/drafts`, …). FastAPI's
default StaticFiles 404s on those because no file matches. We intercept
404s at the catch-all and return `index.html`, which lets React Router
take over. The fallback only applies to non-`/api/...` paths so that
unknown API routes still return their proper 404 JSON.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DIST_DIR = _PROJECT_ROOT / "web_ui" / "dist"


def mount_web_ui(app: FastAPI) -> None:
    """Mount the built SPA at `/` if it exists; otherwise no-op."""
    if not _DIST_DIR.exists():
        # No build present (e.g. fresh checkout before `make build`, or
        # the ci-headless mode that deliberately removes web_ui/). Leave
        # the API surface alone — nothing here errors out.
        return

    index_html = _DIST_DIR / "index.html"

    # Serve hashed asset files (and anything else in dist/) directly.
    app.mount(
        "/assets",
        StaticFiles(directory=_DIST_DIR / "assets"),
        name="web_ui_assets",
    )

    # Catch-all so client-side routes (/inbox, /drafts, ...) load the
    # SPA. We explicitly 404 on /api/* paths that didn't match a real
    # route, so the API surface keeps its proper error semantics instead
    # of silently returning HTML.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="not_found")
        return FileResponse(index_html)
