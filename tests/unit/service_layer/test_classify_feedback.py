"""ClassifyFeedback use case exercised against fake adapters."""

from datetime import datetime, timezone

from adapters.language_models.recorded_response_language_model import (
    RecordedResponseLanguageModel,
    hash_prompt,
)
from adapters.persistence.in_memory_classification_repository import (
    InMemoryClassificationRepository,
)
from adapters.persistence.in_memory_feedback_repository import InMemoryFeedbackRepository
from domain.classification import FeedbackCategory, Sentiment, Severity
from domain.feedback import Feedback, FeedbackChannel, Platform
from service_layer.use_cases.classify_feedback import ClassifyFeedback


def _seed_feedback(repo: InMemoryFeedbackRepository) -> Feedback:
    feedback = Feedback(
        channel=FeedbackChannel.GOOGLE_PLAY,
        app_slug="toi",
        platform=Platform.ANDROID,
        external_id="play_001",
        author_identifier="user@example.com",
        raw_text="App keeps crashing every time I tap a video.",
        received_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )
    repo.add(feedback)
    return feedback


def test_classify_persists_judgment_when_recording_matches():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    feedback = _seed_feedback(feedback_repo)

    # Build the use case once just to get the prompt template, then pre-record
    # the response keyed by the hash of that exact prompt.
    use_case = ClassifyFeedback(
        feedback_repository=feedback_repo,
        classification_repository=classification_repo,
        language_model=RecordedResponseLanguageModel(),  # placeholder
        app_name_lookup={"toi": "Times of India"},
    )
    prompt = use_case.build_prompt(feedback)
    recorded = RecordedResponseLanguageModel(
        recordings={
            hash_prompt(prompt): {
                "category": "bug",
                "sub_category": "video_player_crash",
                "severity": "high",
                "sentiment": "negative",
                "entities": {"feature_name": "video_player"},
                "requires_followup": True,
            }
        }
    )

    use_case = ClassifyFeedback(
        feedback_repository=feedback_repo,
        classification_repository=classification_repo,
        language_model=recorded,
        app_name_lookup={"toi": "Times of India"},
    )
    result = use_case.run()

    assert result.classified == 1
    assert result.failed == 0
    classification = classification_repo.get(feedback.id)
    assert classification is not None
    assert classification.category is FeedbackCategory.BUG
    assert classification.severity is Severity.HIGH
    assert classification.sentiment is Sentiment.NEGATIVE
    assert classification.sub_category == "video_player_crash"
    assert classification.entities == {"feature_name": "video_player"}
    assert classification.requires_followup is True


def test_default_response_is_used_when_prompt_not_recorded():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    _seed_feedback(feedback_repo)

    fallback = RecordedResponseLanguageModel(
        recordings={},
        default_response={
            "category": "other",
            "sub_category": "unrecorded_default",
            "severity": "medium",
            "sentiment": "neutral",
            "entities": {},
            "requires_followup": True,
        },
    )

    use_case = ClassifyFeedback(
        feedback_repository=feedback_repo,
        classification_repository=classification_repo,
        language_model=fallback,
    )
    result = use_case.run()

    assert result.classified == 1
    classifications = list(classification_repo.list_by_app())
    assert len(classifications) == 1
    assert classifications[0].category is FeedbackCategory.OTHER


def test_already_classified_feedback_is_skipped():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    feedback = _seed_feedback(feedback_repo)

    fallback = RecordedResponseLanguageModel(
        recordings={},
        default_response={
            "category": "bug",
            "severity": "low",
            "sentiment": "negative",
            "entities": {},
            "requires_followup": True,
        },
    )

    use_case = ClassifyFeedback(
        feedback_repository=feedback_repo,
        classification_repository=classification_repo,
        language_model=fallback,
    )
    use_case.run()
    second = use_case.run()

    assert second.classified == 0
    assert second.skipped_already_classified == 1
    assert classification_repo.get(feedback.id) is not None  # still there


def test_invalid_language_model_response_is_counted_as_failed():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    _seed_feedback(feedback_repo)

    bad_response = RecordedResponseLanguageModel(
        recordings={},
        default_response={"category": "not_a_real_category", "severity": "high", "sentiment": "negative"},
    )

    use_case = ClassifyFeedback(
        feedback_repository=feedback_repo,
        classification_repository=classification_repo,
        language_model=bad_response,
    )
    result = use_case.run()

    assert result.classified == 0
    assert result.failed == 1
