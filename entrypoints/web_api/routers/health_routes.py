"""GET /api/health — quick health check of the pieces the API depends on.

Checks (each independently):

  * database — can we open a connection and run `SELECT 1`?
  * language_model — is the configured language model healthy?
  * embedding_model — has the local sentence-transformer loaded?
    (Skipped if not yet built; loading it just to health-check would
    pay the ~250 MB cost on every probe.)

Returns 200 with `status="healthy"` if all checks pass; otherwise 200
with `status="degraded"` and per-check details. We deliberately don't
return 503 — a degraded backend is still useful to the dashboard,
which wants to show a warning banner rather than crash.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from entrypoints.composition_root import WiredApp
from entrypoints.web_api.dependencies import wired_app
from entrypoints.web_api.schemas.health_schema import HealthCheck, HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(app: WiredApp = Depends(wired_app)) -> HealthResponse:
    checks: list[HealthCheck] = []

    # Database
    db_check = _check_database(app)
    checks.append(db_check)

    # Language model
    lm_healthy = bool(app.language_model.is_healthy())
    checks.append(
        HealthCheck(
            name="language_model",
            healthy=lm_healthy,
            detail=f"active={getattr(app.language_model, 'active_name', app.language_model.name)}",
        )
    )

    # Embedding model — only report if already loaded; loading it here
    # would defeat the lazy-load design.
    if app._embedding_model is not None:  # type: ignore[attr-defined]
        checks.append(
            HealthCheck(
                name="embedding_model",
                healthy=True,
                detail=f"loaded={app._embedding_model.name}",  # type: ignore[attr-defined]
            )
        )
    else:
        checks.append(
            HealthCheck(
                name="embedding_model",
                healthy=True,
                detail="not_yet_loaded (lazy)",
            )
        )

    status = "healthy" if all(check.healthy for check in checks) else "degraded"
    return HealthResponse(status=status, backend=app.backend_name, checks=checks)


def _check_database(app: WiredApp) -> HealthCheck:
    if app.backend_name != "postgres":
        return HealthCheck(
            name="database",
            healthy=True,
            detail="in_memory (no real database in this process)",
        )
    try:
        from adapters.persistence.database import get_engine

        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return HealthCheck(name="database", healthy=True, detail="postgres reachable")
    except Exception as exc:  # noqa: BLE001
        return HealthCheck(
            name="database",
            healthy=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
