"""Reads the shipped Gmail fixtures (TOI subfolder) and validates the parsed shape."""

from datetime import datetime, timezone
from pathlib import Path

from adapters.feedback_sources.local_gmail_feedback_source import LocalGmailFeedbackSource
from domain.app import App
from domain.feedback import FeedbackChannel, Platform

_TOI_FIXTURES = (
    Path(__file__).resolve().parents[3] / "data_fixtures" / "feedback" / "gmail" / "toi"
)
_TOI_APP = App(slug="toi", name="Times of India")


def test_reads_all_shipped_fixtures():
    source = LocalGmailFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)

    items = list(source.fetch_new(since=None))

    assert len(items) >= 3
    for raw in items:
        assert raw.channel is FeedbackChannel.GMAIL
        assert raw.app_slug == "toi"
        assert raw.platform is Platform.UNKNOWN  # email platform inferred later
        assert raw.external_id
        assert raw.text
        assert raw.received_at.tzinfo is not None


def test_since_filter_excludes_older_items():
    source = LocalGmailFeedbackSource(app=_TOI_APP, fixtures_dir=_TOI_FIXTURES)
    cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)

    assert list(source.fetch_new(since=cutoff)) == []


def test_handles_missing_fixtures_dir(tmp_path):
    source = LocalGmailFeedbackSource(app=_TOI_APP, fixtures_dir=tmp_path / "nope")

    assert list(source.fetch_new(since=None)) == []
