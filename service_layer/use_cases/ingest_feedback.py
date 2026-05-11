"""IngestFeedback — pull new items from each FeedbackSource, dedupe, persist.

One source instance runs per (app, channel) combination. The use case keeps
a per-source cursor so each one resumes independently. Idempotent: rerunning
skips anything already stored. Cursor advance happens after a successful pass
so failures retry from the same point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from domain.feedback import Feedback, FeedbackChannel
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort
from service_layer.ports.feedback_source_port import FeedbackSourcePort


@dataclass(frozen=True)
class IngestFeedbackResult:
    app_slug: str
    channel: FeedbackChannel
    fetched: int
    inserted: int
    duplicates: int


class IngestFeedback:
    def __init__(
        self,
        sources: Sequence[FeedbackSourcePort],
        feedback_repository: FeedbackRepositoryPort,
    ) -> None:
        self._sources = sources
        self._feedback_repository = feedback_repository

    def run(self) -> list[IngestFeedbackResult]:
        return [self._ingest_one(source) for source in self._sources]

    def _ingest_one(self, source: FeedbackSourcePort) -> IngestFeedbackResult:
        cursor = self._feedback_repository.get_cursor(source.channel, source.app_slug)
        fetched = 0
        inserted = 0
        duplicates = 0
        latest_received_at: datetime | None = cursor

        for raw in source.fetch_new(since=cursor):
            fetched += 1
            if self._feedback_repository.exists(raw.channel, raw.app_slug, raw.external_id):
                duplicates += 1
            else:
                self._feedback_repository.add(Feedback.from_raw(raw))
                inserted += 1
            if latest_received_at is None or raw.received_at > latest_received_at:
                latest_received_at = raw.received_at

        if latest_received_at is not None and latest_received_at != cursor:
            self._feedback_repository.update_cursor(
                source.channel, source.app_slug, latest_received_at
            )

        return IngestFeedbackResult(
            app_slug=source.app_slug,
            channel=source.channel,
            fetched=fetched,
            inserted=inserted,
            duplicates=duplicates,
        )
