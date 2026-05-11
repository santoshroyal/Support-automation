"""Feedback endpoints.

  GET /api/feedback                — filtered list (summary shape)
  GET /api/feedback/{feedback_id}  — full detail with classification + draft

Filters on the list endpoint:

  * app           — restrict to one app slug (e.g. ?app=toi)
  * platform     — android | ios | unknown
  * channel      — gmail | google_play | apple_app_store
  * since        — ISO-8601 timestamp; only feedback received after it
  * limit        — page size (default 50, max 200)

Filtering is done at the repository layer for production correctness;
this router just passes the parsed query params through.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from domain.feedback import FeedbackChannel, Platform
from entrypoints.web_api.dependencies import (
    classification_repository,
    draft_reply_repository,
    feedback_repository,
)
from entrypoints.web_api.schemas.feedback_schema import (
    FeedbackDetail,
    FeedbackSummary,
)
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.draft_reply_repository_port import DraftReplyRepositoryPort
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort

router = APIRouter(prefix="/api", tags=["feedback"])


@router.get("/feedback", response_model=list[FeedbackSummary])
def list_feedback(
    app: str | None = Query(default=None, description="App slug, e.g. 'toi'"),
    platform: str | None = Query(default=None, description="android | ios | unknown"),
    channel: str | None = Query(
        default=None, description="gmail | google_play | apple_app_store"
    ),
    since: datetime | None = Query(default=None, description="ISO-8601"),
    limit: int = Query(default=50, ge=1, le=200),
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
    classification_repo: ClassificationRepositoryPort = Depends(
        classification_repository
    ),
    draft_repo: DraftReplyRepositoryPort = Depends(draft_reply_repository),
) -> list[FeedbackSummary]:
    platform_filter = _coerce_platform(platform)
    channel_filter = _coerce_channel(channel)

    rows = list(
        feedback_repo.list_by_filters(
            app_slug=app,
            platform=platform_filter,
            channel=channel_filter,
            since=since,
        )
    )[:limit]

    return [
        FeedbackSummary.from_domain(
            row,
            has_classification=classification_repo.has_classification_for(row.id),
            has_draft=draft_repo.has_draft_for(row.id),
        )
        for row in rows
    ]


@router.get("/feedback/{feedback_id}", response_model=FeedbackDetail)
def get_feedback(
    feedback_id: UUID,
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
    classification_repo: ClassificationRepositoryPort = Depends(
        classification_repository
    ),
    draft_repo: DraftReplyRepositoryPort = Depends(draft_reply_repository),
) -> FeedbackDetail:
    feedback = feedback_repo.get(feedback_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="feedback_not_found")
    classification = classification_repo.get(feedback_id)
    # Find the latest draft for this feedback (any status). The dashboard
    # shows the freshest one regardless of state so the reviewer sees
    # the current state, not stale drafts.
    draft = _latest_draft_for(draft_repo, feedback_id)
    return FeedbackDetail.from_domain(
        feedback, classification=classification, draft=draft
    )


def _coerce_platform(value: str | None) -> Platform | None:
    if value is None:
        return None
    try:
        return Platform(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"invalid_platform: {value!r}. Allowed: {[p.value for p in Platform]}",
        ) from exc


def _coerce_channel(value: str | None) -> FeedbackChannel | None:
    if value is None:
        return None
    try:
        return FeedbackChannel(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"invalid_channel: {value!r}. Allowed: {[c.value for c in FeedbackChannel]}",
        ) from exc


def _latest_draft_for(draft_repo: DraftReplyRepositoryPort, feedback_id: UUID):
    """Return the most recent draft for this feedback, regardless of status."""
    from domain.draft_reply import DraftStatus

    # Check each status in order of "currently meaningful for the reviewer".
    for status in (
        DraftStatus.DRAFT,
        DraftStatus.SENT,
        DraftStatus.EDITED,
        DraftStatus.REGENERATED,
        DraftStatus.REJECTED,
    ):
        for draft in draft_repo.list_by_status(status, limit=200):
            if draft.feedback_id == feedback_id:
                return draft
    return None
