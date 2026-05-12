"""PostgreSQL-backed AuditLogRepository.

Append-only. The port has no update or delete method, and this adapter
doesn't expose either — modifying an audit row would defeat the point
of having an audit trail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import AuditLogOrm
from domain.audit_log import AuditLogEntry


class AuditLogRepositoryPostgres:
    def add(self, entry: AuditLogEntry) -> None:
        with session_scope() as session:
            session.add(
                AuditLogOrm(
                    id=entry.id,
                    actor=entry.actor,
                    action=entry.action,
                    entity_type=entry.entity_type,
                    entity_id=entry.entity_id,
                    details_jsonb=entry.details or None,
                    occurred_at=_ensure_utc(entry.occurred_at),
                )
            )

    def list_recent(
        self,
        since: datetime | None = None,
        actor: str | None = None,
        limit: int = 200,
    ) -> Iterable[AuditLogEntry]:
        with session_scope() as session:
            statement = select(AuditLogOrm).order_by(
                AuditLogOrm.occurred_at.desc()
            )
            if since is not None:
                statement = statement.where(
                    AuditLogOrm.occurred_at >= _ensure_utc(since)
                )
            if actor is not None:
                statement = statement.where(AuditLogOrm.actor == actor)
            statement = statement.limit(limit)
            return [_to_domain(row) for row in session.execute(statement).scalars()]


def _to_domain(row: AuditLogOrm) -> AuditLogEntry:
    return AuditLogEntry(
        id=row.id,
        actor=row.actor,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        details=row.details_jsonb or {},
        occurred_at=row.occurred_at,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
