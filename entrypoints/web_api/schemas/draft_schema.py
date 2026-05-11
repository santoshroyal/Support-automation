"""Draft-endpoint response schemas.

`DraftListItem` is the row a list view renders: enough to show in a
queue (who, when, language, status, preview of the body) without
needing the full citation list. `DraftDetail` is the full shape used by
the single-item endpoint — every citation, the original feedback, the
classification, so the dashboard can render the drill-down without
chaining API calls.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.classification import Classification
from domain.draft_reply import DraftReply
from domain.feedback import Feedback
from entrypoints.web_api.schemas.feedback_schema import (
    CitationSummary,
    ClassificationSummary,
)


class DraftListItem(BaseModel):
    id: UUID
    feedback_id: UUID
    app_slug: str
    platform: str
    channel: str
    language_code: str
    status: str
    body_preview: str = Field(description="First 200 characters of the body")
    citation_count: int = 0
    generated_at: datetime
    sent_at: datetime | None = None

    @classmethod
    def from_domain(cls, draft: DraftReply, feedback: Feedback) -> "DraftListItem":
        preview = (draft.body or "").replace("\n", " ").strip()
        if len(preview) > 200:
            preview = preview[:197] + "..."
        return cls(
            id=draft.id,
            feedback_id=draft.feedback_id,
            app_slug=feedback.app_slug,
            platform=feedback.platform.value,
            channel=feedback.channel.value,
            language_code=draft.language_code,
            status=draft.status.value,
            body_preview=preview,
            citation_count=len(draft.citations),
            generated_at=draft.generated_at,
            sent_at=draft.sent_at,
        )


class DraftDetail(BaseModel):
    id: UUID
    feedback_id: UUID
    app_slug: str
    platform: str
    channel: str
    language_code: str
    status: str
    body: str
    edited_body: str | None = None
    generated_at: datetime
    sent_at: datetime | None = None
    citations: list[CitationSummary] = Field(default_factory=list)
    original_feedback_text: str
    original_feedback_author: str
    original_feedback_received_at: datetime
    classification: ClassificationSummary | None = None

    @classmethod
    def from_domain(
        cls,
        draft: DraftReply,
        *,
        feedback: Feedback,
        classification: Classification | None,
    ) -> "DraftDetail":
        return cls(
            id=draft.id,
            feedback_id=draft.feedback_id,
            app_slug=feedback.app_slug,
            platform=feedback.platform.value,
            channel=feedback.channel.value,
            language_code=draft.language_code,
            status=draft.status.value,
            body=draft.body,
            edited_body=draft.edited_body,
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
            original_feedback_text=feedback.raw_text,
            original_feedback_author=feedback.author_identifier,
            original_feedback_received_at=feedback.received_at,
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
        )
