"""Reads the shipped Google Play fixtures (TOI subfolder) and validates the parsed shape."""

from datetime import datetime, timezone
from pathlib import Path

from adapters.feedback_sources.local_google_play_feedback_source import (
    LocalGooglePlayFeedbackSource,
)
from domain.app import App
from domain.feedback import FeedbackChannel, Platform

_TOI_FIXTURES = (
    Path(__file__).resolve().parents[3] / "data_fixtures" / "feedback" / "play" / "toi"
)
_TOI_APP = App(slug="toi", name="Times of India")


def test_reads_all_shipped_fixtures():
    source = LocalGooglePlayFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)

    items = list(source.fetch_new(since=None))

    assert len(items) >= 3
    for raw in items:
        assert raw.channel is FeedbackChannel.GOOGLE_PLAY
        assert raw.app_slug == "toi"
        assert raw.platform is Platform.ANDROID
        assert raw.external_id
        assert raw.text
        assert raw.received_at.tzinfo is not None
        assert raw.store_review_id == raw.external_id


def test_star_rating_is_preserved_in_metadata():
    source = LocalGooglePlayFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)

    star_ratings = {item.metadata.get("star_rating") for item in source.fetch_new(since=None)}

    assert {1, 5}.issubset(star_ratings)


def test_since_filter_excludes_older_items():
    source = LocalGooglePlayFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)
    cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)

    assert list(source.fetch_new(since=cutoff)) == []


def test_handles_missing_fixtures_dir(tmp_path):
    source = LocalGooglePlayFeedbackSource(app=_TOI_APP, fixtures_dir=tmp_path / "nope")

    assert list(source.fetch_new(since=None)) == []
