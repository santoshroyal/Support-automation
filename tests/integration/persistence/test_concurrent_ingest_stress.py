"""50-thread concurrency stress test for the Postgres-backed ingest pipeline.

This is the test that proves our concurrency design (plan section 8a):

  * Many threads call `IngestFeedback.run()` simultaneously.
  * Each thread sees the SAME source list (same fixtures).
  * After all threads finish:
      - Total rows in the database equal exactly the number of unique
        feedbacks the sources expose. No duplicates, no losses.
      - The cursor for each (channel, app) is exactly the latest fixture's
        received_at — never below it.

If anything ever regresses these guarantees the test fails fast.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pytest

from adapters.persistence.feedback_repository_postgres import FeedbackRepositoryPostgres
from domain.feedback import FeedbackChannel, Platform, RawFeedback
from service_layer.use_cases.ingest_feedback import IngestFeedback


class _StaticSource:
    """A source that hands out the same list of items every time it's asked."""

    def __init__(self, items: list[RawFeedback]) -> None:
        self._items = items

    @property
    def channel(self) -> FeedbackChannel:
        return FeedbackChannel.GOOGLE_PLAY

    @property
    def app_slug(self) -> str:
        return "toi"

    def fetch_new(self, since):
        for raw in self._items:
            if since is None or raw.received_at > since:
                yield raw


def _raw(external_id: str, *, when: datetime) -> RawFeedback:
    return RawFeedback(
        channel=FeedbackChannel.GOOGLE_PLAY,
        app_slug="toi",
        platform=Platform.ANDROID,
        external_id=external_id,
        author_identifier="x",
        text="hello",
        received_at=when,
    )


@pytest.mark.usefixtures("clean_tables")
def test_50_concurrent_ingest_runs_produce_zero_duplicates_and_correct_cursor(engine):  # noqa: ARG001
    """The big one — proves cron-vs-cron overlap is safe."""
    base = datetime(2026, 5, 4, 12, tzinfo=timezone.utc)
    items = [_raw(f"play_{i:03d}", when=base.replace(microsecond=i)) for i in range(20)]
    sources = [_StaticSource(items=items)]

    repository = FeedbackRepositoryPostgres()

    def one_run() -> None:
        # Each thread builds its own use case with the shared repository
        # so they really do hammer the same Postgres rows concurrently.
        IngestFeedback(sources=sources, feedback_repository=repository).run()

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(one_run) for _ in range(50)]
        for future in as_completed(futures):
            future.result()  # surface any exception

    rows = list(repository.list_by_filters())
    external_ids = {row.external_id for row in rows}

    assert len(rows) == 20, f"Expected 20 unique rows, found {len(rows)}"
    assert external_ids == {f"play_{i:03d}" for i in range(20)}

    cursor = repository.get_cursor(FeedbackChannel.GOOGLE_PLAY, "toi")
    expected_max = max(item.received_at for item in items)
    assert cursor == expected_max, f"Cursor regressed: got {cursor}, expected {expected_max}"
