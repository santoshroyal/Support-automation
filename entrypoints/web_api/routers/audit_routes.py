"""Audit log endpoint.

  GET /api/audit  — chronological list of recorded system actions

Read-only. The audit log is append-only at the repository level — there
are no PUT/POST/DELETE endpoints here on purpose, since editable audit
trails defeat the point of having them.

Filters:
  - actor: narrow to one cron job ("draft-replies", "ingest-feedback", ...)
  - since: ISO-8601 lower bound on `occurred_at`
  - limit: page size (default 200, max 1000)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from entrypoints.web_api.dependencies import audit_log_repository
from entrypoints.web_api.schemas.audit_schema import AuditLogItem
from service_layer.ports.audit_log_repository_port import AuditLogRepositoryPort

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/audit", response_model=list[AuditLogItem])
def list_audit_log(
    actor: str | None = Query(default=None, description="e.g. 'draft-replies'"),
    since: datetime | None = Query(default=None, description="ISO-8601"),
    limit: int = Query(default=200, ge=1, le=1000),
    audit_repo: AuditLogRepositoryPort = Depends(audit_log_repository),
) -> list[AuditLogItem]:
    entries = audit_repo.list_recent(since=since, actor=actor, limit=limit)
    return [AuditLogItem.from_domain(entry) for entry in entries]
