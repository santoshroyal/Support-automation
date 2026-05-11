"""Domain invariants for Feedback."""

from datetime import datetime, timezone

from domain.feedback import Feedback, FeedbackChannel, Platform, RawFeedback


def _raw(*, app_slug="toi", platform=Platform.UNKNOWN, external_id="abc123"):
    return RawFeedback(
        channel=FeedbackChannel.GMAIL,
        app_slug=app_slug,
        platform=platform,
        external_id=external_id,
        author_identifier="user@example.com",
        text="hello",
        received_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )


def test_from_raw_copies_channel_app_and_platform():
    raw = _raw(app_slug="et", platform=Platform.ANDROID)

    feedback = Feedback.from_raw(raw)

    assert feedback.channel is FeedbackChannel.GMAIL
    assert feedback.app_slug == "et"
    assert feedback.platform is Platform.ANDROID
    assert feedback.external_id == "abc123"
    assert feedback.dedupe_key == (FeedbackChannel.GMAIL, "et", "abc123")


def test_dedupe_key_distinguishes_channels():
    base_args = dict(
        app_slug="toi",
        platform=Platform.UNKNOWN,
        external_id="same_id",
        author_identifier="x",
        raw_text="x",
        received_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    gmail = Feedback(channel=FeedbackChannel.GMAIL, **base_args)
    play = Feedback(channel=FeedbackChannel.GOOGLE_PLAY, **base_args)

    assert gmail.dedupe_key != play.dedupe_key


def test_dedupe_key_distinguishes_apps():
    """Same external_id from two different apps must not collide."""
    base_args = dict(
        channel=FeedbackChannel.GOOGLE_PLAY,
        platform=Platform.ANDROID,
        external_id="play_review_001",
        author_identifier="x",
        raw_text="x",
        received_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    toi = Feedback(app_slug="toi", **base_args)
    et = Feedback(app_slug="et", **base_args)

    assert toi.dedupe_key != et.dedupe_key
