"""Health-endpoint response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    name: str
    healthy: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(description='"healthy" or "degraded"')
    backend: str = Field(description='"postgres" or "in_memory"')
    checks: list[HealthCheck]
