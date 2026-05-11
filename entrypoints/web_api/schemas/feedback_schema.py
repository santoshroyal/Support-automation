"""Feedback-endpoint response schemas.

`FeedbackSummary` is the small shape used by list endpoints — enough for
a dashboard row but without the full body or classification details.

`FeedbackDetail` is the full shape used by the single-item endpoint —
includes classification, cluster id, and draft (if any) so the
dashboard's drill-down view doesn't need to make extra API calls.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.classification import Classification
from domain.draft_reply import DraftReply
from domain.feedback import Feedback


class ClassificationSummary(BaseModel):
    category: str
    sub_category: str | None = None
    severity: str
    sentiment: str
    requires_followup: bool
    classified_at: datetime
    language_model_used: str


class CitationSummary(BaseModel):
    knowledge_chunk_id: UUID
    source_url: str | None = None
    source_title: str
    snippet: str


class DraftSummary(BaseModel):
    id: UUID
    language_code: str
    body: str
    status: str
    generated_at: datetime
    sent_at: datetime | None = None
    citations: list[CitationSummary] = Field(default_factory=list)


class FeedbackSummary(BaseModel):
    id: UUID
    app_slug: str
    platform: str
    channel: str
    external_id: str
    author_identifier: str
    raw_text_preview: str = Field(description="First 200 characters of the body")
    received_at: datetime
    language_code: str | None = None
    has_classification: bool = False
    has_draft: bool = False

    @classmethod
    def from_domain(
        cls,
        feedback: Feedback,
        *,
        has_classification: bool,
        has_draft: bool,
    ) -> "FeedbackSummary":
        preview = (feedback.raw_text or "").replace("\n", " ").strip()
        if len(preview) > 200:
            preview = preview[:197] + "..."
        return cls(
            id=feedback.id,
            app_slug=feedback.app_slug,
            platform=feedback.platform.value,
            channel=feedback.channel.value,
            external_id=feedback.external_id,
            author_identifier=feedback.author_identifier,
            raw_text_preview=preview,
            received_at=feedback.received_at,
            language_code=feedback.language_code,
            has_classification=has_classification,
            has_draft=has_draft,
        )


class FeedbackDetail(BaseModel):
    id: UUID
    app_slug: str
    platform: str
    channel: str
    external_id: str
    author_identifier: str
    raw_text: str
    received_at: datetime
    language_code: str | None = None
    app_version: str | None = None
    device_info: str | None = None
    classification: ClassificationSummary | None = None
    draft: DraftSummary | None = None

    @classmethod
    def from_domain(
        cls,
        feedback: Feedback,
        *,
        classification: Classification | None,
        draft: DraftReply | None,
    ) -> "FeedbackDetail":
        return cls(
            id=feedback.id,
            app_slug=feedback.app_slug,
            platform=feedback.platform.value,
            channel=feedback.channel.value,
            external_id=feedback.external_id,
            author_identifier=feedback.author_identifier,
            raw_text=feedback.raw_text,
            received_at=feedback.received_at,
            language_code=feedback.language_code,
            app_version=feedback.app_version,
            device_info=feedback.device_info,
            classification=(
                ClassificationSummary(
                    category=classification.category.value,
                    sub_category=classification.sub_category,
                    severity=classification.severity.value,
                    sentiment=classification.sentiment.value,
                    requires_followup=classification.requires_followup,
                    classified_at=classification.classified_at,
                    language_model_used=classification.language_model_used,
                )
                if classification
                else None
            ),
            draft=(
                DraftSummary(
                    id=draft.id,
                    language_code=draft.language_code,
                    body=draft.body,
                    status=draft.status.value,
                    generated_at=draft.generated_at,
                    sent_at=draft.sent_at,
                    citations=[
                        CitationSummary(
                            knowledge_chunk_id=c.knowledge_chunk_id,
                            source_url=c.source_url,
                            source_title=c.source_title,
                            snippet=c.snippet,
                        )
                        for c in draft.citations
                    ],
                )
                if draft
                else None
            ),
        )
