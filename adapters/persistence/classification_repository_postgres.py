"""PostgreSQL-backed ClassificationRepository.

Implements `ClassificationRepositoryPort` exactly as the in-memory version
does, plus an actual SQL join when the use case needs to know which
feedback is unclassified.

Concurrency design: the only writer is the classifier cron job (one
in-flight at a time via the cron advisory lock). Inserts use
`INSERT ... ON CONFLICT (feedback_id) DO UPDATE` so re-running the
classifier replaces an old judgment with a fresh one without raising.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import ClassificationOrm, FeedbackOrm
from domain.classification import (
    Classification,
    FeedbackCategory,
    Sentiment,
    Severity,
)


class ClassificationRepositoryPostgres:
    def add(self, classification: Classification) -> None:
        with session_scope() as session:
            statement = (
                pg_insert(ClassificationOrm)
                .values(
                    feedback_id=classification.feedback_id,
                    category=classification.category.value,
                    sub_category=classification.sub_category,
                    severity=classification.severity.value,
                    sentiment=classification.sentiment.value,
                    requires_followup=classification.requires_followup,
                    entities_jsonb=classification.entities or None,
                    language_model_used=classification.language_model_used,
                    classified_at=_ensure_utc(classification.classified_at),
                )
                .on_conflict_do_update(
                    index_elements=[ClassificationOrm.feedback_id],
                    set_={
                        "category": classification.category.value,
                        "sub_category": classification.sub_category,
                        "severity": classification.severity.value,
                        "sentiment": classification.sentiment.value,
                        "requires_followup": classification.requires_followup,
                        "entities_jsonb": classification.entities or None,
                        "language_model_used": classification.language_model_used,
                        "classified_at": _ensure_utc(classification.classified_at),
                    },
                )
            )
            session.execute(statement)

    def get(self, feedback_id: UUID) -> Classification | None:
        with session_scope() as session:
            row = session.get(ClassificationOrm, feedback_id)
            return _to_domain(row) if row else None

    def has_classification_for(self, feedback_id: UUID) -> bool:
        with session_scope() as session:
            statement = select(ClassificationOrm.feedback_id).where(
                ClassificationOrm.feedback_id == feedback_id
            )
            return session.execute(statement).first() is not None

    def list_by_app(self, app_slug: str | None = None) -> Iterable[Classification]:
        with session_scope() as session:
            statement = select(ClassificationOrm)
            if app_slug is not None:
                statement = statement.join(
                    FeedbackOrm, FeedbackOrm.id == ClassificationOrm.feedback_id
                ).where(FeedbackOrm.app_slug == app_slug)
            return [_to_domain(row) for row in session.execute(statement).scalars()]


def _to_domain(row: ClassificationOrm) -> Classification:
    return Classification(
        feedback_id=row.feedback_id,
        category=FeedbackCategory(row.category),
        severity=Severity(row.severity),
        sentiment=Sentiment(row.sentiment),
        sub_category=row.sub_category,
        entities=dict(row.entities_jsonb or {}),
        requires_followup=row.requires_followup,
        language_model_used=row.language_model_used,
        classified_at=row.classified_at,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
