"""Filtering on the in-memory repository.

This proves the dashboard's filter contract works at the port layer. The
Postgres-backed repository has to satisfy the same contract.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from adapters.persistence.in_memory_feedback_repository import InMemoryFeedbackRepository
from domain.feedback import Feedback, FeedbackChannel, Platform


def _build(*, app_slug, platform, channel, external_id, when):
    return Feedback(
        channel=channel,
        app_slug=app_slug,
        platform=platform,
        external_id=external_id,
        author_identifier="x",
        raw_text="x",
        received_at=when,
        id=uuid4(),
    )


def _seeded_repo():
    repo = InMemoryFeedbackRepository()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    rows = [
        ("toi", Platform.ANDROID, FeedbackChannel.GOOGLE_PLAY, "p1"),
        ("toi", Platform.IOS, FeedbackChannel.APPLE_APP_STORE, "a1"),
        ("toi", Platform.UNKNOWN, FeedbackChannel.GMAIL, "g1"),
        ("et", Platform.ANDROID, FeedbackChannel.GOOGLE_PLAY, "p2"),
        ("et", Platform.IOS, FeedbackChannel.APPLE_APP_STORE, "a2"),
        ("nbt", Platform.ANDROID, FeedbackChannel.GOOGLE_PLAY, "p3"),
    ]
    for offset, (app_slug, platform, channel, external_id) in enumerate(rows):
        repo.add(
            _build(
                app_slug=app_slug,
                platform=platform,
                channel=channel,
                external_id=external_id,
                when=base + timedelta(minutes=offset),
            )
        )
    return repo


def test_no_filters_returns_everything():
    repo = _seeded_repo()
    assert len(list(repo.list_by_filters())) == 6


def test_filter_by_app():
    repo = _seeded_repo()
    toi = list(repo.list_by_filters(app_slug="toi"))
    assert len(toi) == 3
    assert {f.app_slug for f in toi} == {"toi"}


def test_filter_by_platform():
    repo = _seeded_repo()
    android_only = list(repo.list_by_filters(platform=Platform.ANDROID))
    assert len(android_only) == 3
    assert {f.platform for f in android_only} == {Platform.ANDROID}


def test_filter_by_channel():
    repo = _seeded_repo()
    play_only = list(repo.list_by_filters(channel=FeedbackChannel.GOOGLE_PLAY))
    assert len(play_only) == 3


def test_filters_combine():
    repo = _seeded_repo()
    toi_android = list(repo.list_by_filters(app_slug="toi", platform=Platform.ANDROID))
    assert len(toi_android) == 1
    assert toi_android[0].external_id == "p1"


def test_filter_by_since():
    repo = _seeded_repo()
    cutoff = datetime(2026, 5, 1, 0, 3, tzinfo=timezone.utc)
    fresh = list(repo.list_by_filters(since=cutoff))
    assert len(fresh) == 2  # only the last two minute-offsets (4 and 5) are after :03
