"""FeedbackRepositoryPostgres satisfies the same contract as the in-memory one,
plus survives across sessions, plus enforces dedupe atomically.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from domain.feedback import Feedback, FeedbackChannel, Platform


def _build(*, app_slug, platform, channel, external_id, when, text="hello"):
    return Feedback(
        channel=channel,
        app_slug=app_slug,
        platform=platform,
        external_id=external_id,
        author_identifier="user@example.com",
        raw_text=text,
        received_at=when,
        id=uuid4(),
    )


@pytest.fixture
def repo(clean_tables):
    from adapters.persistence.feedback_repository_postgres import (
        FeedbackRepositoryPostgres,
    )

    return FeedbackRepositoryPostgres()


def test_add_and_get_round_trips(repo):
    feedback = _build(
        app_slug="toi",
        platform=Platform.ANDROID,
        channel=FeedbackChannel.GOOGLE_PLAY,
        external_id="play_001",
        when=datetime(2026, 5, 4, 10, tzinfo=timezone.utc),
    )

    repo.add(feedback)
    fetched = repo.get(feedback.id)

    assert fetched is not None
    assert fetched.app_slug == "toi"
    assert fetched.platform is Platform.ANDROID
    assert fetched.channel is FeedbackChannel.GOOGLE_PLAY


def test_duplicate_inserts_are_silently_skipped(repo):
    feedback = _build(
        app_slug="toi",
        platform=Platform.ANDROID,
        channel=FeedbackChannel.GOOGLE_PLAY,
        external_id="play_dup",
        when=datetime(2026, 5, 4, 10, tzinfo=timezone.utc),
    )
    repo.add(feedback)

    duplicate = _build(
        app_slug="toi",
        platform=Platform.ANDROID,
        channel=FeedbackChannel.GOOGLE_PLAY,
        external_id="play_dup",  # same dedupe key
        when=datetime(2026, 5, 4, 10, tzinfo=timezone.utc),
        text="different body",
    )
    # Different UUID, same dedupe key — must NOT insert a second row.
    repo.add(duplicate)

    rows = list(repo.list_by_filters())
    assert len(rows) == 1
    # The first one wins; the database refused the second on the unique constraint.
    assert rows[0].id == feedback.id


def test_filters_combine(repo):
    base = datetime(2026, 5, 4, tzinfo=timezone.utc)
    rows = [
        ("toi", Platform.ANDROID, FeedbackChannel.GOOGLE_PLAY, "p1"),
        ("toi", Platform.IOS, FeedbackChannel.APPLE_APP_STORE, "a1"),
        ("et", Platform.ANDROID, FeedbackChannel.GOOGLE_PLAY, "p2"),
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

    toi_android = list(repo.list_by_filters(app_slug="toi", platform=Platform.ANDROID))
    assert len(toi_android) == 1
    assert toi_android[0].external_id == "p1"


def test_cursor_round_trips_and_uses_greatest(repo):
    base = datetime(2026, 5, 4, 12, tzinfo=timezone.utc)

    repo.update_cursor(FeedbackChannel.GOOGLE_PLAY, "toi", base)
    repo.update_cursor(FeedbackChannel.GOOGLE_PLAY, "toi", base + timedelta(minutes=10))
    # A "slow" writer arrives with an older timestamp — must NOT regress.
    repo.update_cursor(FeedbackChannel.GOOGLE_PLAY, "toi", base + timedelta(minutes=5))

    assert repo.get_cursor(FeedbackChannel.GOOGLE_PLAY, "toi") == base + timedelta(minutes=10)


def test_cursors_are_independent_per_channel_and_app(repo):
    base = datetime(2026, 5, 4, 12, tzinfo=timezone.utc)
    repo.update_cursor(FeedbackChannel.GOOGLE_PLAY, "toi", base)
    repo.update_cursor(FeedbackChannel.APPLE_APP_STORE, "et", base + timedelta(hours=1))

    assert repo.get_cursor(FeedbackChannel.GOOGLE_PLAY, "toi") == base
    assert (
        repo.get_cursor(FeedbackChannel.APPLE_APP_STORE, "et")
        == base + timedelta(hours=1)
    )
    # Unset cursors are None.
    assert repo.get_cursor(FeedbackChannel.GMAIL, "nbt") is None
