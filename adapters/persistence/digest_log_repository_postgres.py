"""PostgreSQL-backed DigestLogRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import DigestLogOrm
from service_layer.ports.digest_log_repository_port import DigestLogEntry


class DigestLogRepositoryPostgres:
    def add(self, entry: DigestLogEntry) -> None:
        with session_scope() as session:
            session.add(
                DigestLogOrm(
                    id=entry.id,
                    type=entry.type,
                    body_html=entry.body_html,
                    recipients_jsonb=list(entry.recipients) if entry.recipients else None,
                    sent_at=_ensure_utc(entry.sent_at),
                    error=entry.error,
                )
            )

    def list_recent(self, since: datetime) -> Iterable[DigestLogEntry]:
        cutoff = _ensure_utc(since)
        with session_scope() as session:
            statement = (
                select(DigestLogOrm)
                .where(DigestLogOrm.sent_at >= cutoff)
                .order_by(DigestLogOrm.sent_at.desc())
            )
            return [
                DigestLogEntry(
                    id=row.id,
                    type=row.type,
                    body_html=row.body_html,
                    recipients=list(row.recipients_jsonb or []),
                    sent_at=row.sent_at,
                    error=row.error,
                )
                for row in session.execute(statement).scalars()
            ]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
