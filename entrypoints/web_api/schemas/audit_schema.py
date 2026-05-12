"""Audit-log response schema.

One shape used by both the list endpoint and the dashboard. The `details`
field is a free-form dict because each call site records different
metadata (counts, fix versions, recipient lists) — the dashboard just
renders the key/value pairs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from domain.audit_log import AuditLogEntry


class AuditLogItem(BaseModel):
    id: UUID
    actor: str
    action: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime

    @classmethod
    def from_domain(cls, entry: AuditLogEntry) -> "AuditLogItem":
        return cls(
            id=entry.id,
            actor=entry.actor,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            details=entry.details or {},
            occurred_at=entry.occurred_at,
        )
