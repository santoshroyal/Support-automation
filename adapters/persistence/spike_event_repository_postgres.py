"""PostgreSQL-backed SpikeEventRepository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import select

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import SpikeEventOrm
from domain.spike_event import SpikeEvent


class SpikeEventRepositoryPostgres:
    def add(self, event: SpikeEvent) -> None:
        with session_scope() as session:
            session.add(
                SpikeEventOrm(
                    id=event.id,
                    cluster_id=event.cluster_id,
                    window_start=_ensure_utc(event.window_start),
                    window_end=_ensure_utc(event.window_end),
                    count=event.count,
                    baseline=event.baseline,
                    ratio=event.ratio,
                    sample_feedback_ids_jsonb=[str(fid) for fid in event.sample_feedback_ids]
                    if event.sample_feedback_ids
                    else None,
                    alerted_at=_ensure_utc(event.alerted_at) if event.alerted_at else None,
                )
            )

    def has_recent_event_for(self, cluster_id: UUID, within_seconds: int) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
        with session_scope() as session:
            statement = select(SpikeEventOrm.id).where(
                SpikeEventOrm.cluster_id == cluster_id,
                SpikeEventOrm.window_end >= cutoff,
            )
            return session.execute(statement).first() is not None

    def list_recent(self, since: datetime) -> Iterable[SpikeEvent]:
        cutoff = _ensure_utc(since)
        with session_scope() as session:
            statement = (
                select(SpikeEventOrm)
                .where(SpikeEventOrm.window_end >= cutoff)
                .order_by(SpikeEventOrm.window_end.desc())
            )
            return [_to_domain(row) for row in session.execute(statement).scalars()]

    def get(self, spike_id: UUID) -> SpikeEvent | None:
        with session_scope() as session:
            statement = select(SpikeEventOrm).where(SpikeEventOrm.id == spike_id)
            row = session.execute(statement).scalar_one_or_none()
            return _to_domain(row) if row is not None else None


def _to_domain(row: SpikeEventOrm) -> SpikeEvent:
    return SpikeEvent(
        id=row.id,
        cluster_id=row.cluster_id,
        window_start=row.window_start,
        window_end=row.window_end,
        count=row.count,
        baseline=row.baseline,
        ratio=row.ratio,
        sample_feedback_ids=[UUID(fid) for fid in (row.sample_feedback_ids_jsonb or [])],
        alerted_at=row.alerted_at,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
