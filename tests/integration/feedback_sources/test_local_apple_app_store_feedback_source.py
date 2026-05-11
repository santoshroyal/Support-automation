"""Reads the shipped Apple App Store fixtures (TOI subfolder) and validates the parsed shape."""

from datetime import datetime, timezone
from pathlib import Path

from adapters.feedback_sources.local_apple_app_store_feedback_source import (
    LocalAppleAppStoreFeedbackSource,
)
from domain.app import App
from domain.feedback import FeedbackChannel, Platform

_TOI_FIXTURES = (
    Path(__file__).resolve().parents[3] / "data_fixtures" / "feedback" / "apple" / "toi"
)
_TOI_APP = App(slug="toi", name="Times of India")


def test_reads_all_shipped_fixtures():
    source = LocalAppleAppStoreFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)

    items = list(source.fetch_new(since=None))

    assert len(items) >= 3
    for raw in items:
        assert raw.channel is FeedbackChannel.APPLE_APP_STORE
        assert raw.app_slug == "toi"
        assert raw.platform is Platform.IOS
        assert raw.external_id
        assert raw.text  # combined title + body
        assert raw.received_at.tzinfo is not None


def test_combines_title_and_body_into_text():
    source = LocalAppleAppStoreFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)

    items = list(source.fetch_new(since=None))
    audio_briefings = next(
        item for item in items if item.external_id == "apple_review_2026_05_04_001"
    )

    assert "Audio briefings won't play" in audio_briefings.text
    assert "Tapping play just spins forever" in audio_briefings.text


def test_territory_is_preserved_in_metadata():
    source = LocalAppleAppStoreFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)

    territories = {item.metadata.get("territory") for item in source.fetch_new(since=None)}

    assert "IND" in territories
    assert "GBR" in territories


def test_since_filter_excludes_older_items():
    source = LocalAppleAppStoreFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)
    cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)

    assert list(source.fetch_new(since=cutoff)) == []
