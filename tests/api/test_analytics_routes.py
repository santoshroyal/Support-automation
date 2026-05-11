"""Analytics endpoints — volume + categories."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from adapters.persistence.in_memory_classification_repository import (
    InMemoryClassificationRepository,
)
from adapters.persistence.in_memory_feedback_repository import (
    InMemoryFeedbackRepository,
)
from domain.classification import (
    Classification,
    FeedbackCategory,
    Sentiment,
    Severity,
)
from domain.feedback import Feedback, FeedbackChannel, Platform
from entrypoints.composition_root import reset_app_for_tests
from entrypoints.web_api.dependencies import (
    classification_repository,
    feedback_repository,
)
from entrypoints.web_api.main import create_app


@pytest.fixture
def seeded():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    now = datetime.now(timezone.utc)

    feedbacks = [
        Feedback(
            channel=FeedbackChannel.GMAIL,
            app_slug="toi",
            platform=Platform.UNKNOWN,
            external_id="m1",
            author_identifier="a@example.com",
            raw_text="crash",
            received_at=now - timedelta(hours=2),
            language_code="en",
        ),
        Feedback(
            channel=FeedbackChannel.GMAIL,
            app_slug="toi",
            platform=Platform.UNKNOWN,
            external_id="m2",
            author_identifier="b@example.com",
            raw_text="font small",
            received_at=now - timedelta(hours=3),
            language_code="en",
        ),
        Feedback(
            channel=FeedbackChannel.GOOGLE_PLAY,
            app_slug="et",
            platform=Platform.ANDROID,
            external_id="p1",
            author_identifier="MarketPro",
            raw_text="lag",
            received_at=now - timedelta(days=1, hours=2),
            language_code="en",
        ),
        Feedback(
            channel=FeedbackChannel.GOOGLE_PLAY,
            app_slug="nbt",
            platform=Platform.ANDROID,
            external_id="p2",
            author_identifier="reader",
            raw_text="ads",
            # 10 days old — outside the default 7-day range_days
            received_at=now - timedelta(days=10),
            language_code="hi",
        ),
    ]
    for feedback in feedbacks:
        feedback_repo.add(feedback)

    classification_repo.add(
        Classification(
            feedback_id=feedbacks[0].id,
            category=FeedbackCategory.BUG,
            severity=Severity.HIGH,
            sentiment=Sentiment.NEGATIVE,
            sub_category="video_crash",
            requires_followup=True,
            language_model_used="recorded",
        )
    )
    classification_repo.add(
        Classification(
            feedback_id=feedbacks[1].id,
            category=FeedbackCategory.BUG,
            severity=Severity.LOW,
            sentiment=Sentiment.NEGATIVE,
            sub_category="font_size",
            requires_followup=True,
            language_model_used="recorded",
        )
    )
    classification_repo.add(
        Classification(
            feedback_id=feedbacks[2].id,
            category=FeedbackCategory.FEATURE_REQUEST,
            severity=Severity.MEDIUM,
            sentiment=Sentiment.NEGATIVE,
            sub_category="real_time_quotes",
            requires_followup=True,
            language_model_used="recorded",
        )
    )
    return feedbacks, feedback_repo, classification_repo


def _client(seeded):
    _, feedback_repo, classification_repo = seeded
    reset_app_for_tests()
    app = create_app()
    app.dependency_overrides[feedback_repository] = lambda: feedback_repo
    app.dependency_overrides[classification_repository] = lambda: classification_repo
    return TestClient(app)


def test_volume_buckets_count_each_day(seeded):
    client = _client(seeded)

    response = client.get("/api/analytics/volume?range_days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["range_days"] == 7
    total = sum(bucket["total"] for bucket in body["buckets"])
    # Three feedbacks inside the 7-day window; the 10-day-old one is excluded.
    assert total == 3


def test_volume_includes_breakdown_by_channel(seeded):
    client = _client(seeded)

    response = client.get("/api/analytics/volume?range_days=7")

    body = response.json()
    channels = {}
    for bucket in body["buckets"]:
        for channel, count in bucket["by_channel"].items():
            channels[channel] = channels.get(channel, 0) + count
    assert channels == {"gmail": 2, "google_play": 1}


def test_volume_app_filter_narrows_results(seeded):
    client = _client(seeded)

    response = client.get("/api/analytics/volume?range_days=7&app=toi")

    body = response.json()
    total = sum(bucket["total"] for bucket in body["buckets"])
    assert total == 2


def test_volume_invalid_range_days_rejected(seeded):
    client = _client(seeded)

    response = client.get("/api/analytics/volume?range_days=999")

    assert response.status_code == 422  # FastAPI Query validation


def test_categories_groups_by_category_and_sub_category(seeded):
    client = _client(seeded)

    response = client.get("/api/analytics/categories?range_days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["total_classified_feedback"] == 3
    counts = {entry["sub_category"]: entry["count"] for entry in body["categories"]}
    assert counts == {
        "video_crash": 1,
        "font_size": 1,
        "real_time_quotes": 1,
    }


def test_categories_severity_breakdown(seeded):
    client = _client(seeded)

    response = client.get("/api/analytics/categories?range_days=7")

    by_sub = {entry["sub_category"]: entry for entry in response.json()["categories"]}
    assert by_sub["video_crash"]["severity_breakdown"] == {"high": 1}
    assert by_sub["font_size"]["severity_breakdown"] == {"low": 1}
