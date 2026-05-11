"""Feedback list + detail endpoints.

These tests use the in-memory backend (no DATABASE_URL set) and seed
the repositories via dependency overrides — that way they exercise the
HTTP layer without needing Postgres or any cron runs to have happened.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from adapters.persistence.in_memory_classification_repository import (
    InMemoryClassificationRepository,
)
from adapters.persistence.in_memory_draft_reply_repository import (
    InMemoryDraftReplyRepository,
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
from domain.draft_reply import DraftReply
from domain.feedback import Feedback, FeedbackChannel, Platform
from entrypoints.composition_root import reset_app_for_tests
from entrypoints.web_api.dependencies import (
    classification_repository,
    draft_reply_repository,
    feedback_repository,
)
from entrypoints.web_api.main import create_app


@pytest.fixture
def seeded_repositories():
    """Build three in-memory repositories with two feedbacks (one classified + drafted)."""
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()

    feedback_a = Feedback(
        channel=FeedbackChannel.GMAIL,
        app_slug="toi",
        platform=Platform.UNKNOWN,
        external_id="m1",
        author_identifier="user@example.com",
        raw_text="Video player keeps crashing on iPhone 14 after the latest update.",
        received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        language_code="en",
    )
    feedback_b = Feedback(
        channel=FeedbackChannel.GOOGLE_PLAY,
        app_slug="et",
        platform=Platform.ANDROID,
        external_id="p1",
        author_identifier="MarketPro123",
        raw_text="Live market data is lagging by minutes. Fix this.",
        received_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        language_code="en",
    )
    feedback_repo.add(feedback_a)
    feedback_repo.add(feedback_b)

    classification_repo.add(
        Classification(
            feedback_id=feedback_a.id,
            category=FeedbackCategory.BUG,
            severity=Severity.HIGH,
            sentiment=Sentiment.NEGATIVE,
            sub_category="video_player_crash",
            requires_followup=True,
            language_model_used="recorded",
        )
    )

    draft_repo.add(
        DraftReply(
            feedback_id=feedback_a.id,
            language_code="en",
            body="Sorry about the crash — fix in v8.4.",
        )
    )

    return feedback_a, feedback_b, feedback_repo, classification_repo, draft_repo


def _client_with(seeded):
    _, _, feedback_repo, classification_repo, draft_repo = seeded
    reset_app_for_tests()
    app = create_app()
    app.dependency_overrides[feedback_repository] = lambda: feedback_repo
    app.dependency_overrides[classification_repository] = lambda: classification_repo
    app.dependency_overrides[draft_reply_repository] = lambda: draft_repo
    return TestClient(app)


def test_list_returns_summary_for_every_seeded_feedback(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/feedback")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    apps = {item["app_slug"] for item in items}
    assert apps == {"toi", "et"}


def test_app_filter_narrows_results(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/feedback?app=toi")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["app_slug"] == "toi"


def test_platform_filter(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/feedback?platform=android")

    items = response.json()
    assert {item["platform"] for item in items} == {"android"}


def test_channel_filter(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/feedback?channel=gmail")

    items = response.json()
    assert {item["channel"] for item in items} == {"gmail"}


def test_invalid_platform_returns_400(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/feedback?platform=not_a_real_platform")

    assert response.status_code == 400
    assert "invalid_platform" in response.text


def test_has_classification_and_has_draft_flags(seeded_repositories):
    feedback_a, feedback_b, *_ = seeded_repositories
    client = _client_with(seeded_repositories)

    response = client.get("/api/feedback")
    by_id = {UUID(item["id"]): item for item in response.json()}

    assert by_id[feedback_a.id]["has_classification"] is True
    assert by_id[feedback_a.id]["has_draft"] is True
    assert by_id[feedback_b.id]["has_classification"] is False
    assert by_id[feedback_b.id]["has_draft"] is False


def test_detail_endpoint_returns_classification_and_draft(seeded_repositories):
    feedback_a, *_ = seeded_repositories
    client = _client_with(seeded_repositories)

    response = client.get(f"/api/feedback/{feedback_a.id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == str(feedback_a.id)
    assert detail["classification"]["category"] == "bug"
    assert detail["classification"]["severity"] == "high"
    assert detail["draft"]["status"] == "draft"
    assert "v8.4" in detail["draft"]["body"]


def test_detail_404_for_unknown_feedback(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get(f"/api/feedback/{uuid4()}")

    assert response.status_code == 404


def test_limit_caps_list_size(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/feedback?limit=1")

    assert len(response.json()) == 1
