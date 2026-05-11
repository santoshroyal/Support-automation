"""PostgreSQL-backed DraftReplyRepository.

Idempotency: re-running the drafter for the same feedback creates a new
`draft` row, but only if no `sent` row already exists. We never overwrite
a draft a human accepted. Earlier `draft` rows for the same feedback are
demoted to `regenerated` so the dashboard only shows the freshest one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import select, update

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import DraftReplyOrm
from domain.draft_reply import Citation, DraftReply, DraftStatus


class DraftReplyRepositoryPostgres:
    def add(self, draft: DraftReply) -> None:
        with session_scope() as session:
            # Demote earlier active drafts for the same feedback.
            session.execute(
                update(DraftReplyOrm)
                .where(
                    DraftReplyOrm.feedback_id == draft.feedback_id,
                    DraftReplyOrm.status == DraftStatus.DRAFT.value,
                )
                .values(status=DraftStatus.REGENERATED.value)
            )
            session.add(
                DraftReplyOrm(
                    id=draft.id,
                    feedback_id=draft.feedback_id,
                    language_code=draft.language_code,
                    body=draft.body,
                    citations_jsonb=_citations_to_json(draft.citations),
                    status=draft.status.value,
                    edited_body=draft.edited_body,
                    generated_at=_ensure_utc(draft.generated_at),
                    sent_at=_ensure_utc(draft.sent_at) if draft.sent_at else None,
                    metadata_jsonb=draft.metadata or None,
                )
            )

    def get(self, draft_id: UUID) -> DraftReply | None:
        with session_scope() as session:
            row = session.get(DraftReplyOrm, draft_id)
            return _to_domain(row) if row else None

    def list_by_status(
        self, status: DraftStatus, limit: int = 100
    ) -> Iterable[DraftReply]:
        with session_scope() as session:
            statement = (
                select(DraftReplyOrm)
                .where(DraftReplyOrm.status == status.value)
                .order_by(DraftReplyOrm.generated_at.desc())
                .limit(limit)
            )
            return [_to_domain(row) for row in session.execute(statement).scalars()]

    def has_draft_for(self, feedback_id: UUID) -> bool:
        with session_scope() as session:
            statement = select(DraftReplyOrm.id).where(
                DraftReplyOrm.feedback_id == feedback_id,
                DraftReplyOrm.status.in_(
                    [
                        DraftStatus.DRAFT.value,
                        DraftStatus.SENT.value,
                        DraftStatus.EDITED.value,
                    ]
                ),
            )
            return session.execute(statement).first() is not None

    def update_status(
        self,
        draft_id: UUID,
        status: DraftStatus,
        edited_body: str | None = None,
    ) -> None:
        with session_scope() as session:
            values: dict = {"status": status.value}
            if edited_body is not None:
                values["edited_body"] = edited_body
            if status is DraftStatus.SENT:
                values["sent_at"] = datetime.now(timezone.utc)
            session.execute(
                update(DraftReplyOrm).where(DraftReplyOrm.id == draft_id).values(**values)
            )


def _citations_to_json(citations: list[Citation]) -> list | None:
    if not citations:
        return None
    return [
        {
            "knowledge_chunk_id": str(c.knowledge_chunk_id),
            "source_url": c.source_url,
            "source_title": c.source_title,
            "snippet": c.snippet,
        }
        for c in citations
    ]


def _to_domain(row: DraftReplyOrm) -> DraftReply:
    citations = []
    if row.citations_jsonb:
        for entry in row.citations_jsonb:
            citations.append(
                Citation(
                    knowledge_chunk_id=UUID(entry["knowledge_chunk_id"]),
                    source_url=entry.get("source_url"),
                    source_title=entry.get("source_title", ""),
                    snippet=entry.get("snippet", ""),
                )
            )
    return DraftReply(
        id=row.id,
        feedback_id=row.feedback_id,
        language_code=row.language_code,
        body=row.body,
        citations=citations,
        status=DraftStatus(row.status),
        generated_at=row.generated_at,
        sent_at=row.sent_at,
        edited_body=row.edited_body,
        metadata=dict(row.metadata_jsonb or {}),
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
