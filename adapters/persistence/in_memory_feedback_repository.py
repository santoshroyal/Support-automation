"""In-memory FeedbackRepository — used during early-phase development and tests.

Implements the same Protocol as the future Postgres-backed repository, so the
service layer doesn't change when we swap implementations.

Filtering is naive (linear scan); fine for local dev and tests where we have
at most a few thousand fixture records. The Postgres repository will use
indexed queries for production-scale volumes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from domain.feedback import Feedback, FeedbackChannel, Platform


class InMemoryFeedbackRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, Feedback] = {}
        self._by_dedupe_key: dict[tuple[FeedbackChannel, str, str], UUID] = {}
        # Cursors keyed by (channel, app_slug) so each source instance has its own.
        self._cursors: dict[tuple[FeedbackChannel, str], datetime] = {}

    def add(self, feedback: Feedback) -> None:
        if feedback.dedupe_key in self._by_dedupe_key:
            return
        self._by_id[feedback.id] = feedback
        self._by_dedupe_key[feedback.dedupe_key] = feedback.id

    def exists(self, channel: FeedbackChannel, app_slug: str, external_id: str) -> bool:
        return (channel, app_slug, external_id) in self._by_dedupe_key

    def get(self, feedback_id: UUID) -> Feedback | None:
        return self._by_id.get(feedback_id)

    def list_by_filters(
        self,
        app_slug: str | None = None,
        platform: Platform | None = None,
        channel: FeedbackChannel | None = None,
        since: datetime | None = None,
    ) -> Iterable[Feedback]:
        for feedback in self._by_id.values():
            if app_slug is not None and feedback.app_slug != app_slug:
                continue
            if platform is not None and feedback.platform is not platform:
                continue
            if channel is not None and feedback.channel is not channel:
                continue
            if since is not None and feedback.received_at <= since:
                continue
            yield feedback

    def list_unclassified(
        self, app_slug: str | None = None, limit: int = 100
    ) -> Iterable[Feedback]:
        # Without classifications stored, treat every feedback as unclassified.
        # The Postgres repo will join against the classification table.
        count = 0
        for feedback in self._by_id.values():
            if app_slug is not None and feedback.app_slug != app_slug:
                continue
            yield feedback
            count += 1
            if count >= limit:
                break

    def get_cursor(self, channel: FeedbackChannel, app_slug: str) -> datetime | None:
        return self._cursors.get((channel, app_slug))

    def update_cursor(
        self, channel: FeedbackChannel, app_slug: str, cursor: datetime
    ) -> None:
        self._cursors[(channel, app_slug)] = cursor

    def __len__(self) -> int:
        return len(self._by_id)
