"""Draft endpoints.

  GET /api/drafts                 — filtered list (preview shape)
  GET /api/drafts/{draft_id}      — full draft + original feedback + classification

Filters on the list endpoint mirror the feedback list: app, platform,
channel, since, limit. Drafts are listed in reverse-chronological order
of `generated_at`, which is what the queue view wants — the freshest at
the top.

The drafter only writes one draft per feedback in phase 1 (re-running
the cron skips already-drafted feedbacks), so "the latest draft for
this feedback" is well-defined. If we ever introduce regeneration the
list_by_status iteration in `_latest_draft_for` will continue to pick
the freshest entry by `generated_at`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from domain.draft_reply import DraftStatus
from domain.feedback import FeedbackChannel, Platform
from entrypoints.web_api.dependencies import (
    classification_repository,
    draft_reply_repository,
    feedback_repository,
)
from entrypoints.web_api.schemas.draft_schema import DraftDetail, DraftListItem
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.draft_reply_repository_port import DraftReplyRepositoryPort
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort

router = APIRouter(prefix="/api", tags=["drafts"])


@router.get("/drafts", response_model=list[DraftListItem])
def list_drafts(
    app: str | None = Query(default=None, description="App slug, e.g. 'toi'"),
    platform: str | None = Query(default=None, description="android | ios | unknown"),
    channel: str | None = Query(
        default=None, description="gmail | google_play | apple_app_store"
    ),
    status: str | None = Query(
        default=None, description="draft | sent | edited | rejected | regenerated"
    ),
    since: datetime | None = Query(
        default=None, description="ISO-8601 — only drafts generated after this time"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
    draft_repo: DraftReplyRepositoryPort = Depends(draft_reply_repository),
) -> list[DraftListItem]:
    platform_filter = _coerce_platform(platform)
    channel_filter = _coerce_channel(channel)
    status_filter = _coerce_status(status)

    feedbacks_by_id = {
        feedback.id: feedback
        for feedback in feedback_repo.list_by_filters(
            app_slug=app,
            platform=platform_filter,
            channel=channel_filter,
        )
    }

    statuses_to_scan = (
        [status_filter] if status_filter is not None else list(DraftStatus)
    )
    drafts: list = []
    for draft_status in statuses_to_scan:
        for draft in draft_repo.list_by_status(draft_status, limit=500):
            if draft.feedback_id not in feedbacks_by_id:
                continue
            if since is not None and draft.generated_at < since:
                continue
            drafts.append(draft)

    drafts.sort(key=lambda d: d.generated_at, reverse=True)
    drafts = drafts[:limit]

    return [
        DraftListItem.from_domain(draft, feedbacks_by_id[draft.feedback_id])
        for draft in drafts
    ]


@router.get("/drafts/{draft_id}", response_model=DraftDetail)
def get_draft(
    draft_id: UUID,
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
    classification_repo: ClassificationRepositoryPort = Depends(
        classification_repository
    ),
    draft_repo: DraftReplyRepositoryPort = Depends(draft_reply_repository),
) -> DraftDetail:
    draft = draft_repo.get(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft_not_found")
    feedback = feedback_repo.get(draft.feedback_id)
    if feedback is None:
        # The foreign key invariant says this shouldn't happen, but if it
        # does we'd rather return 404 than crash with KeyError on
        # `feedback.app_slug`.
        raise HTTPException(status_code=404, detail="feedback_not_found")
    classification = classification_repo.get(draft.feedback_id)
    return DraftDetail.from_domain(
        draft, feedback=feedback, classification=classification
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


def _coerce_status(value: str | None) -> DraftStatus | None:
    if value is None:
        return None
    try:
        return DraftStatus(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"invalid_status: {value!r}. Allowed: {[s.value for s in DraftStatus]}",
        ) from exc
