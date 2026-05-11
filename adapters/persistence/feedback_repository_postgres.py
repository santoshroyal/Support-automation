"""PostgreSQL-backed FeedbackRepository.

Implements `FeedbackRepositoryPort` exactly as the in-memory version does, so
the use cases never know which is plugged in.

Concurrency design (plan section 8a):
- Inserts use `INSERT ... ON CONFLICT (channel, app_slug, external_id) DO NOTHING`
  so two concurrent ingest passes can never produce duplicates, no matter how
  the timing falls.
- Cursor updates use `GREATEST(cursor_value, :new)` so a slower writer that
  arrives second cannot regress the cursor below a faster writer's progress.
- Every method opens its own short-lived session via `session_scope()`; reads
  rely on Postgres MVCC so they don't block writers and vice versa.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import ClassificationOrm, FeedbackOrm, IngestionCursorOrm
from domain.feedback import Feedback, FeedbackChannel, Platform


class FeedbackRepositoryPostgres:
    def add(self, feedback: Feedback) -> None:
        with session_scope() as session:
            statement = pg_insert(FeedbackOrm).values(
                id=feedback.id,
                channel=feedback.channel.value,
                app_slug=feedback.app_slug,
                platform=feedback.platform.value,
                external_id=feedback.external_id,
                author_identifier=feedback.author_identifier,
                raw_text=feedback.raw_text,
                normalised_text=feedback.normalised_text,
                language_code=feedback.language_code,
                app_version=feedback.app_version,
                device_info=feedback.device_info,
                gmail_thread_id=feedback.gmail_thread_id,
                store_review_id=feedback.store_review_id,
                received_at=_ensure_utc(feedback.received_at),
                created_at=_ensure_utc(feedback.created_at),
                metadata_jsonb=None,
            ).on_conflict_do_nothing(constraint="uq_feedback_dedupe")
            session.execute(statement)

    def exists(self, channel: FeedbackChannel, app_slug: str, external_id: str) -> bool:
        with session_scope() as session:
            statement = select(FeedbackOrm.id).where(
                and_(
                    FeedbackOrm.channel == channel.value,
                    FeedbackOrm.app_slug == app_slug,
                    FeedbackOrm.external_id == external_id,
                )
            )
            return session.execute(statement).first() is not None

    def get(self, feedback_id: UUID) -> Feedback | None:
        with session_scope() as session:
            row = session.get(FeedbackOrm, feedback_id)
            return _to_domain(row) if row else None

    def list_by_filters(
        self,
        app_slug: str | None = None,
        platform: Platform | None = None,
        channel: FeedbackChannel | None = None,
        since: datetime | None = None,
    ) -> Iterable[Feedback]:
        with session_scope() as session:
            statement = select(FeedbackOrm)
            if app_slug is not None:
                statement = statement.where(FeedbackOrm.app_slug == app_slug)
            if platform is not None:
                statement = statement.where(FeedbackOrm.platform == platform.value)
            if channel is not None:
                statement = statement.where(FeedbackOrm.channel == channel.value)
            if since is not None:
                statement = statement.where(FeedbackOrm.received_at > _ensure_utc(since))
            statement = statement.order_by(FeedbackOrm.received_at.desc())
            return [_to_domain(row) for row in session.execute(statement).scalars()]

    def list_unclassified(
        self, app_slug: str | None = None, limit: int = 100
    ) -> Iterable[Feedback]:
        """Yield feedback that has no classification row yet.

        Implemented as a LEFT OUTER JOIN: feedback rows without a matching
        classification row are the ones still to process. The classifier
        re-runs on the same set are idempotent because the use case checks
        `has_classification_for` and the repository's INSERT is upsert-safe.
        """
        with session_scope() as session:
            statement = (
                select(FeedbackOrm)
                .outerjoin(ClassificationOrm, ClassificationOrm.feedback_id == FeedbackOrm.id)
                .where(ClassificationOrm.feedback_id.is_(None))
                .order_by(FeedbackOrm.received_at.asc())
                .limit(limit)
            )
            if app_slug is not None:
                statement = statement.where(FeedbackOrm.app_slug == app_slug)
            return [_to_domain(row) for row in session.execute(statement).scalars()]

    def get_cursor(self, channel: FeedbackChannel, app_slug: str) -> datetime | None:
        with session_scope() as session:
            row = session.get(IngestionCursorOrm, (channel.value, app_slug))
            return row.cursor_value if row else None

    def update_cursor(
        self, channel: FeedbackChannel, app_slug: str, cursor: datetime
    ) -> None:
        new_value = _ensure_utc(cursor)
        with session_scope() as session:
            now = datetime.now(timezone.utc)
            statement = (
                pg_insert(IngestionCursorOrm)
                .values(
                    channel=channel.value,
                    app_slug=app_slug,
                    cursor_value=new_value,
                    last_run_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[IngestionCursorOrm.channel, IngestionCursorOrm.app_slug],
                    # GREATEST() prevents a slow writer from regressing a
                    # faster writer's progress.
                    set_={
                        "cursor_value": _greatest_cursor(),
                        "last_run_at": now,
                    },
                )
            )
            session.execute(statement)


def _to_domain(row: FeedbackOrm) -> Feedback:
    return Feedback(
        id=row.id,
        channel=FeedbackChannel(row.channel),
        app_slug=row.app_slug,
        platform=Platform(row.platform),
        external_id=row.external_id,
        author_identifier=row.author_identifier,
        raw_text=row.raw_text,
        normalised_text=row.normalised_text,
        language_code=row.language_code,
        app_version=row.app_version,
        device_info=row.device_info,
        gmail_thread_id=row.gmail_thread_id,
        store_review_id=row.store_review_id,
        received_at=row.received_at,
        created_at=row.created_at,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _greatest_cursor():
    """SQL fragment used inside `on_conflict_do_update.set_` to pick the later cursor."""
    from sqlalchemy import func

    excluded = pg_insert(IngestionCursorOrm).excluded
    return func.greatest(IngestionCursorOrm.cursor_value, excluded.cursor_value)
