"""FastAPI app factory.

The app is created via `create_app()` so tests can construct fresh
instances with isolated state. The default `app` global at module
bottom is what uvicorn loads in production:

    .venv/bin/uvicorn entrypoints.web_api.main:app --host 127.0.0.1 --port 8080

Why `FastAPIOffline` instead of the standard `FastAPI`:
The standard `FastAPI()` ships its built-in `/api/docs` page that
loads Swagger UI's JavaScript and CSS from a public CDN (jsdelivr.net)
at runtime. On corporate networks that block that CDN, the page hangs
indefinitely with a blank screen. `FastAPIOffline` bundles the same
Swagger UI + ReDoc assets as part of the package and serves them from
the FastAPI process itself — no external network calls. Every other
behaviour (routes, schemas, OpenAPI generation) is identical to plain
FastAPI.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi_offline import FastAPIOffline

from entrypoints.web_api.error_handlers import register_error_handlers
from entrypoints.web_api.routers import (
    analytics_routes,
    apps_routes,
    draft_routes,
    feedback_routes,
    health_routes,
    knowledge_routes,
    spike_routes,
)


def create_app() -> FastAPI:
    app = FastAPIOffline(
        title="Times of India — Support Automation API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.include_router(health_routes.router)
    app.include_router(apps_routes.router)
    app.include_router(feedback_routes.router)
    app.include_router(draft_routes.router)
    app.include_router(spike_routes.router)
    app.include_router(knowledge_routes.router)
    app.include_router(analytics_routes.router)

    register_error_handlers(app)
    return app


app = create_app()
