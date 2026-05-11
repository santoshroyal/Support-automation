"""IngestFeedback exercised against fake adapters.

The use case is pure orchestration; we verify dedupe, cursor advancement
per (channel × app), and that result records are accurate.
"""

from datetime import datetime, timedelta, timezone

import pytest

from adapters.persistence.in_memory_feedback_repository import InMemoryFeedbackRepository
from domain.feedback import Feedback, FeedbackChannel, Platform, RawFeedback
from service_layer.use_cases.ingest_feedback import IngestFeedback


class _StaticGmailSource:
    channel = FeedbackChannel.GMAIL

    def __init__(self, app_slug: str, items: list[RawFeedback]) -> None:
        self.app_slug = app_slug
        self._items = items

    def fetch_new(self, since):
        for raw in self._items:
            if since is None or raw.received_at > since:
                yield raw


def _raw(external_id: str, *, when: datetime, app_slug: str = "toi") -> RawFeedback:
    return RawFeedback(
        channel=FeedbackChannel.GMAIL,
        app_slug=app_slug,
        platform=Platform.UNKNOWN,
        external_id=external_id,
        author_identifier="user@example.com",
        text="hello",
        received_at=when,
    )


def test_inserts_new_feedback_and_advances_cursor():
    base = datetime(2026, 4, 30, tzinfo=timezone.utc)
    source = _StaticGmailSource(
        app_slug="toi",
        items=[_raw("a", when=base), _raw("b", when=base + timedelta(minutes=5))],
    )
    repository = InMemoryFeedbackRepository()

    results = IngestFeedback(sources=[source], feedback_repository=repository).run()

    assert len(results) == 1
    assert results[0].app_slug == "toi"
    assert results[0].channel is FeedbackChannel.GMAIL
    assert results[0].fetched == 2
    assert results[0].inserted == 2
    assert results[0].duplicates == 0
    assert len(repository) == 2
    assert repository.get_cursor(FeedbackChannel.GMAIL, "toi") == base + timedelta(minutes=5)


def test_skips_duplicates_already_in_repository():
    base = datetime(2026, 4, 30, tzinfo=timezone.utc)
    repository = InMemoryFeedbackRepository()
    repository.add(
        Feedback(
            channel=FeedbackChannel.GMAIL,
            app_slug="toi",
            platform=Platform.UNKNOWN,
            external_id="a",
            author_identifier="user@example.com",
            raw_text="seeded",
            received_at=base,
        )
    )

    source = _StaticGmailSource(
        app_slug="toi",
        items=[_raw("a", when=base), _raw("b", when=base + timedelta(minutes=1))],
    )
    results = IngestFeedback(sources=[source], feedback_repository=repository).run()

    assert results[0].fetched == 2
    assert results[0].inserted == 1
    assert results[0].duplicates == 1


def test_per_app_cursors_are_independent():
    """A run for TOI must not move ET's cursor."""
    base = datetime(2026, 4, 30, tzinfo=timezone.utc)
    repository = InMemoryFeedbackRepository()

    toi_source = _StaticGmailSource(
        app_slug="toi",
        items=[_raw("toi_1", when=base, app_slug="toi")],
    )
    et_source = _StaticGmailSource(
        app_slug="et",
        items=[_raw("et_1", when=base + timedelta(hours=2), app_slug="et")],
    )
    IngestFeedback(sources=[toi_source, et_source], feedback_repository=repository).run()

    assert repository.get_cursor(FeedbackChannel.GMAIL, "toi") == base
    assert repository.get_cursor(FeedbackChannel.GMAIL, "et") == base + timedelta(hours=2)


def test_same_external_id_across_apps_is_not_a_duplicate():
    base = datetime(2026, 4, 30, tzinfo=timezone.utc)
    repository = InMemoryFeedbackRepository()
    sources = [
        _StaticGmailSource("toi", [_raw("shared_id", when=base, app_slug="toi")]),
        _StaticGmailSource("et", [_raw("shared_id", when=base, app_slug="et")]),
    ]

    results = IngestFeedback(sources=sources, feedback_repository=repository).run()

    by_app = {r.app_slug: r for r in results}
    assert by_app["toi"].inserted == 1
    assert by_app["et"].inserted == 1
    assert len(repository) == 2


def test_second_run_with_advanced_cursor_skips_old_items():
    base = datetime(2026, 4, 30, tzinfo=timezone.utc)
    repository = InMemoryFeedbackRepository()
    items = [_raw("a", when=base), _raw("b", when=base + timedelta(minutes=10))]
    use_case = IngestFeedback(
        sources=[_StaticGmailSource("toi", items)], feedback_repository=repository
    )

    use_case.run()
    second = use_case.run()

    assert second[0].fetched == 0
    assert second[0].inserted == 0
    assert second[0].duplicates == 0


@pytest.mark.parametrize("count", [0, 5])
def test_handles_arbitrary_input_sizes(count):
    base = datetime(2026, 4, 30, tzinfo=timezone.utc)
    items = [_raw(f"id_{i}", when=base + timedelta(minutes=i)) for i in range(count)]
    use_case = IngestFeedback(
        sources=[_StaticGmailSource("toi", items)],
        feedback_repository=InMemoryFeedbackRepository(),
    )
    results = use_case.run()
    assert results[0].inserted == count
