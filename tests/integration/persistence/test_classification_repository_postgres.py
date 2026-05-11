"""ClassificationRepositoryPostgres satisfies the same contract as the in-memory one."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.classification import (
    Classification,
    FeedbackCategory,
    Sentiment,
    Severity,
)
from domain.feedback import Feedback, FeedbackChannel, Platform


@pytest.fixture
def repos(clean_tables):
    from adapters.persistence.classification_repository_postgres import (
        ClassificationRepositoryPostgres,
    )
    from adapters.persistence.feedback_repository_postgres import (
        FeedbackRepositoryPostgres,
    )

    return FeedbackRepositoryPostgres(), ClassificationRepositoryPostgres()


def _seed_feedback(repo, app_slug="toi") -> Feedback:
    feedback = Feedback(
        channel=FeedbackChannel.GOOGLE_PLAY,
        app_slug=app_slug,
        platform=Platform.ANDROID,
        external_id=f"play_{uuid4().hex[:8]}",
        author_identifier="user@example.com",
        raw_text="App keeps crashing.",
        received_at=datetime(2026, 5, 4, 10, tzinfo=timezone.utc),
    )
    repo.add(feedback)
    return feedback


def test_add_then_get_round_trips(repos):
    feedback_repo, classification_repo = repos
    feedback = _seed_feedback(feedback_repo)

    classification = Classification(
        feedback_id=feedback.id,
        category=FeedbackCategory.BUG,
        severity=Severity.HIGH,
        sentiment=Sentiment.NEGATIVE,
        sub_category="video_crash",
        entities={"feature": "video_player"},
        language_model_used="recorded",
    )
    classification_repo.add(classification)

    fetched = classification_repo.get(feedback.id)
    assert fetched is not None
    assert fetched.category is FeedbackCategory.BUG
    assert fetched.severity is Severity.HIGH
    assert fetched.entities == {"feature": "video_player"}


def test_re_classification_overwrites_existing_row(repos):
    feedback_repo, classification_repo = repos
    feedback = _seed_feedback(feedback_repo)

    first = Classification(
        feedback_id=feedback.id,
        category=FeedbackCategory.OTHER,
        severity=Severity.LOW,
        sentiment=Sentiment.NEUTRAL,
        language_model_used="recorded",
    )
    classification_repo.add(first)

    second = Classification(
        feedback_id=feedback.id,
        category=FeedbackCategory.BUG,
        severity=Severity.CRITICAL,
        sentiment=Sentiment.NEGATIVE,
        language_model_used="claude_code",
    )
    classification_repo.add(second)

    fetched = classification_repo.get(feedback.id)
    assert fetched.category is FeedbackCategory.BUG
    assert fetched.severity is Severity.CRITICAL
    assert fetched.language_model_used == "claude_code"


def test_list_unclassified_skips_classified(repos):
    feedback_repo, classification_repo = repos
    classified_feedback = _seed_feedback(feedback_repo, app_slug="toi")
    unclassified_feedback = _seed_feedback(feedback_repo, app_slug="toi")

    classification_repo.add(
        Classification(
            feedback_id=classified_feedback.id,
            category=FeedbackCategory.BUG,
            severity=Severity.MEDIUM,
            sentiment=Sentiment.NEGATIVE,
            language_model_used="recorded",
        )
    )

    pending = list(feedback_repo.list_unclassified())
    pending_ids = {fb.id for fb in pending}

    assert unclassified_feedback.id in pending_ids
    assert classified_feedback.id not in pending_ids


def test_list_by_app_filters_via_join(repos):
    feedback_repo, classification_repo = repos
    toi = _seed_feedback(feedback_repo, app_slug="toi")
    et = _seed_feedback(feedback_repo, app_slug="et")

    for feedback in (toi, et):
        classification_repo.add(
            Classification(
                feedback_id=feedback.id,
                category=FeedbackCategory.BUG,
                severity=Severity.LOW,
                sentiment=Sentiment.NEGATIVE,
                language_model_used="recorded",
            )
        )

    toi_only = list(classification_repo.list_by_app(app_slug="toi"))
    assert len(toi_only) == 1
    assert toi_only[0].feedback_id == toi.id
