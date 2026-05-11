"""Draft list + detail endpoints.

Tests use in-memory repositories, seeded via dependency overrides, so
the HTTP layer is exercised without Postgres or cron runs.
"""

from datetime import datetime, timezone
from uuid import uuid4

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
from domain.draft_reply import Citation, DraftReply, DraftStatus
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
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()

    feedback_a = Feedback(
        channel=FeedbackChannel.GMAIL,
        app_slug="toi",
        platform=Platform.UNKNOWN,
        external_id="m1",
        author_identifier="user@example.com",
        raw_text="Video player keeps crashing.",
        received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        language_code="en",
    )
    feedback_b = Feedback(
        channel=FeedbackChannel.GOOGLE_PLAY,
        app_slug="et",
        platform=Platform.ANDROID,
        external_id="p1",
        author_identifier="MarketPro123",
        raw_text="Live market data is lagging.",
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

    draft_a = DraftReply(
        feedback_id=feedback_a.id,
        language_code="en",
        body="Sorry about the crash — fix in v8.4.",
        citations=[
            Citation(
                knowledge_chunk_id=uuid4(),
                source_url="https://confluence.internal/page/123",
                source_title="Video crash known issue",
                snippet="Fix in v8.4 rolling out next week.",
            )
        ],
        generated_at=datetime(2026, 5, 6, 10, tzinfo=timezone.utc),
    )
    draft_b = DraftReply(
        feedback_id=feedback_b.id,
        language_code="en",
        body="Quote refresh fix in v5.7.3.",
        generated_at=datetime(2026, 5, 7, 9, tzinfo=timezone.utc),
        status=DraftStatus.SENT,
        sent_at=datetime(2026, 5, 7, 10, tzinfo=timezone.utc),
    )
    draft_repo.add(draft_a)
    draft_repo.add(draft_b)

    return feedback_a, feedback_b, draft_a, draft_b, feedback_repo, classification_repo, draft_repo


def _client_with(seeded):
    *_, feedback_repo, classification_repo, draft_repo = seeded
    reset_app_for_tests()
    app = create_app()
    app.dependency_overrides[feedback_repository] = lambda: feedback_repo
    app.dependency_overrides[classification_repository] = lambda: classification_repo
    app.dependency_overrides[draft_reply_repository] = lambda: draft_repo
    return TestClient(app)


def test_list_returns_both_drafts_newest_first(seeded_repositories):
    _, _, _, draft_b, *_ = seeded_repositories
    client = _client_with(seeded_repositories)

    response = client.get("/api/drafts")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    # draft_b is newer (May 7) — should appear first
    assert items[0]["id"] == str(draft_b.id)


def test_list_filtered_by_app(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/drafts?app=toi")

    items = response.json()
    assert len(items) == 1
    assert items[0]["app_slug"] == "toi"


def test_list_filtered_by_status_sent(seeded_repositories):
    _, _, _, draft_b, *_ = seeded_repositories
    client = _client_with(seeded_repositories)

    response = client.get("/api/drafts?status=sent")

    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(draft_b.id)
    assert items[0]["status"] == "sent"


def test_list_invalid_status_returns_400(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get("/api/drafts?status=nonexistent_status")

    assert response.status_code == 400
    assert "invalid_status" in response.text


def test_detail_returns_full_draft_with_citations(seeded_repositories):
    _, _, draft_a, *_ = seeded_repositories
    client = _client_with(seeded_repositories)

    response = client.get(f"/api/drafts/{draft_a.id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == str(draft_a.id)
    assert "v8.4" in detail["body"]
    assert len(detail["citations"]) == 1
    assert detail["citations"][0]["source_title"] == "Video crash known issue"
    assert detail["classification"]["category"] == "bug"


def test_detail_404_for_unknown_draft(seeded_repositories):
    client = _client_with(seeded_repositories)

    response = client.get(f"/api/drafts/{uuid4()}")

    assert response.status_code == 404
