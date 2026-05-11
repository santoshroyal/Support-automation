"""DraftFeedbackReply use case exercised against fake adapters."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from adapters.persistence.in_memory_classification_repository import (
    InMemoryClassificationRepository,
)
from adapters.persistence.in_memory_draft_reply_repository import (
    InMemoryDraftReplyRepository,
)
from adapters.persistence.in_memory_feedback_repository import InMemoryFeedbackRepository
from adapters.retrieval.in_memory_knowledge_retriever import InMemoryKnowledgeRetriever
from domain.classification import Classification, FeedbackCategory, Sentiment, Severity
from domain.draft_reply import DraftStatus
from domain.feedback import Feedback, FeedbackChannel, Platform
from service_layer.use_cases.draft_feedback_reply import DraftFeedbackReply


class _CapturingDelivery:
    name = "fake"

    def __init__(self) -> None:
        self.delivered: list[tuple[Feedback, object]] = []

    def deliver(self, feedback, draft):
        self.delivered.append((feedback, draft))


class _ScriptedLanguageModel:
    """Returns the configured JSON payload on every prompt."""

    name = "scripted"

    def __init__(self, payload: dict, capture_prompt: bool = True) -> None:
        self.payload = payload
        self.last_prompt: str | None = None

    def is_healthy(self) -> bool:
        return True

    def complete(self, prompt, schema=None):
        self.last_prompt = prompt
        return json.dumps(self.payload)


class _SimpleEmbedder:
    dimension = 1

    def embed(self, text: str) -> list[float]:
        return [1.0]

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


def _seed(feedback_repo, classification_repo, *, requires_followup=True) -> Feedback:
    feedback = Feedback(
        channel=FeedbackChannel.GMAIL,
        app_slug="toi",
        platform=Platform.UNKNOWN,
        external_id="m1",
        author_identifier="user@example.com",
        raw_text="Video player keeps crashing on iPhone 14 after the latest update.",
        received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        language_code="en",
    )
    feedback_repo.add(feedback)
    classification_repo.add(
        Classification(
            feedback_id=feedback.id,
            category=FeedbackCategory.BUG,
            severity=Severity.HIGH,
            sentiment=Sentiment.NEGATIVE,
            sub_category="video_player_crash",
            requires_followup=requires_followup,
            language_model_used="scripted",
        )
    )
    return feedback


def _build_drafter(
    feedback_repo, classification_repo, draft_repo, retriever, lm, delivery
):
    return DraftFeedbackReply(
        feedback_repository=feedback_repo,
        classification_repository=classification_repo,
        draft_reply_repository=draft_repo,
        knowledge_retriever=retriever,
        language_model=lm,
        reply_delivery=delivery,
        app_name_lookup={"toi": "Times of India"},
    )


def test_drafts_a_reply_and_persists_with_citations():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    feedback = _seed(feedback_repo, classification_repo)

    retriever = InMemoryKnowledgeRetriever(_SimpleEmbedder())
    chunk_id = uuid4()
    retriever.index(
        knowledge_chunk_id=chunk_id,
        knowledge_document_id=uuid4(),
        content="TOI-4521: video player crashes on iOS 17.4+. Fix in v8.4.",
        source_url="https://example.com/toi-4521",
        source_title="TOI-4521",
    )
    delivery = _CapturingDelivery()
    lm = _ScriptedLanguageModel(
        {
            "language_code": "en",
            "body": "Sorry about the video crash — fix in v8.4 next week [1].",
            "cited_chunk_indices": [1],
        }
    )

    drafter = _build_drafter(
        feedback_repo, classification_repo, draft_repo, retriever, lm, delivery
    )
    result = drafter.run()

    assert result.drafted == 1
    assert len(draft_repo) == 1
    [(delivered_feedback, draft)] = delivery.delivered
    assert delivered_feedback.id == feedback.id
    assert "v8.4" in draft.body
    assert len(draft.citations) == 1
    assert draft.citations[0].knowledge_chunk_id == chunk_id


def test_skips_when_no_classification():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    feedback_repo.add(
        Feedback(
            channel=FeedbackChannel.GMAIL,
            app_slug="toi",
            platform=Platform.UNKNOWN,
            external_id="m1",
            author_identifier="x",
            raw_text="hi",
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )
    drafter = _build_drafter(
        feedback_repo,
        classification_repo,
        draft_repo,
        InMemoryKnowledgeRetriever(_SimpleEmbedder()),
        _ScriptedLanguageModel({}),
        _CapturingDelivery(),
    )

    result = drafter.run()

    assert result.drafted == 0
    assert result.skipped_no_classification == 1


def test_skips_when_classification_says_no_followup():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    _seed(feedback_repo, classification_repo, requires_followup=False)

    drafter = _build_drafter(
        feedback_repo,
        classification_repo,
        draft_repo,
        InMemoryKnowledgeRetriever(_SimpleEmbedder()),
        _ScriptedLanguageModel({}),
        _CapturingDelivery(),
    )
    result = drafter.run()

    assert result.drafted == 0
    assert result.skipped_no_followup == 1


def test_skips_when_draft_already_exists():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    _seed(feedback_repo, classification_repo)
    retriever = InMemoryKnowledgeRetriever(_SimpleEmbedder())
    delivery = _CapturingDelivery()
    lm = _ScriptedLanguageModel(
        {"language_code": "en", "body": "hi", "cited_chunk_indices": []}
    )

    drafter = _build_drafter(
        feedback_repo, classification_repo, draft_repo, retriever, lm, delivery
    )
    drafter.run()
    second = drafter.run()

    assert second.drafted == 0
    assert second.skipped_already_drafted == 1


def test_invalid_json_response_is_counted_as_failed():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    _seed(feedback_repo, classification_repo)

    class _BrokenLM:
        name = "broken"

        def is_healthy(self):
            return True

        def complete(self, prompt, schema=None):
            return "not valid json"

    drafter = _build_drafter(
        feedback_repo,
        classification_repo,
        draft_repo,
        InMemoryKnowledgeRetriever(_SimpleEmbedder()),
        _BrokenLM(),
        _CapturingDelivery(),
    )
    result = drafter.run()

    assert result.drafted == 0
    assert result.failed == 1


def test_empty_body_is_counted_as_failed():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    _seed(feedback_repo, classification_repo)

    drafter = _build_drafter(
        feedback_repo,
        classification_repo,
        draft_repo,
        InMemoryKnowledgeRetriever(_SimpleEmbedder()),
        _ScriptedLanguageModel(
            {"language_code": "en", "body": "  ", "cited_chunk_indices": []}
        ),
        _CapturingDelivery(),
    )
    result = drafter.run()

    assert result.failed == 1


def test_re_drafting_demotes_old_draft_to_regenerated():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    feedback = _seed(feedback_repo, classification_repo)
    retriever = InMemoryKnowledgeRetriever(_SimpleEmbedder())
    delivery = _CapturingDelivery()
    first_lm = _ScriptedLanguageModel(
        {"language_code": "en", "body": "first draft", "cited_chunk_indices": []}
    )
    drafter = _build_drafter(
        feedback_repo, classification_repo, draft_repo, retriever, first_lm, delivery
    )
    drafter.run()
    [first_draft] = list(draft_repo.list_by_status(DraftStatus.DRAFT))

    # Simulate the operator deleting the existing draft (e.g. via dashboard)
    # so the drafter is allowed to run again, then re-draft.
    draft_repo.update_status(first_draft.id, DraftStatus.REJECTED)

    second_lm = _ScriptedLanguageModel(
        {"language_code": "en", "body": "second draft", "cited_chunk_indices": []}
    )
    _build_drafter(
        feedback_repo, classification_repo, draft_repo, retriever, second_lm, delivery
    ).run()

    actives = list(draft_repo.list_by_status(DraftStatus.DRAFT))
    assert len(actives) == 1
    assert actives[0].body == "second draft"
