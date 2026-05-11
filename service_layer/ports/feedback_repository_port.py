"""Port for persisting and retrieving Feedback aggregates.

The repository is filterable by app, platform, and channel. The dashboard
calls these filter methods directly; the use cases also use them when they
need to scope work to a particular app or platform (e.g. spike detection
runs per app).

Cursors are kept per (channel, app_slug) — each source instance resumes from
its own last position so adding a new app doesn't reset others.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol
from uuid import UUID

from domain.feedback import Feedback, FeedbackChannel, Platform


class FeedbackRepositoryPort(Protocol):
    def add(self, feedback: Feedback) -> None: ...

    def exists(self, channel: FeedbackChannel, app_slug: str, external_id: str) -> bool: ...

    def get(self, feedback_id: UUID) -> Feedback | None: ...

    def list_by_filters(
        self,
        app_slug: str | None = None,
        platform: Platform | None = None,
        channel: FeedbackChannel | None = None,
        since: datetime | None = None,
    ) -> Iterable[Feedback]:
        """Filter combinator. Any field left as None means 'all values'."""
        ...

    def list_unclassified(
        self,
        app_slug: str | None = None,
        limit: int = 100,
    ) -> Iterable[Feedback]: ...

    def get_cursor(self, channel: FeedbackChannel, app_slug: str) -> datetime | None: ...

    def update_cursor(
        self, channel: FeedbackChannel, app_slug: str, cursor: datetime
    ) -> None: ...
