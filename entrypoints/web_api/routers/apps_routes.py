"""GET /api/apps — list every configured Times Internet app.

The dashboard uses this to populate the app filter dropdown so the
support team can switch between Times of India / Economic Times /
Navbharat Times views.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from adapters.settings.app_registry import AppRegistry
from entrypoints.web_api.dependencies import app_registry
from entrypoints.web_api.schemas.app_schema import AppResponse

router = APIRouter(prefix="/api", tags=["apps"])


@router.get("/apps", response_model=list[AppResponse])
def list_apps(registry: AppRegistry = Depends(app_registry)) -> list[AppResponse]:
    return [AppResponse.from_domain(app) for app in registry.all()]
