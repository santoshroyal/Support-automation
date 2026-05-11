"""Analytics endpoints.

  GET /api/analytics/volume      — daily volume buckets with channel/platform/app breakdown
  GET /api/analytics/categories  — counts grouped by classification.category

Both endpoints accept the same scope filters as the rest of the API
(`app`, `platform`, `channel`) plus a `range_days` parameter that
defaults to 7. The maximum lookback is 90 days — beyond that, the
dashboard should reach for a dedicated analytics tool rather than the
live read API.

The aggregations run in Python over filtered repository reads. At phase-1
volumes (single-digit thousand feedbacks total) this is fine; the per-
query cost is dominated by ORM round-trip, not aggregation. When that
stops being true, the work moves into SQL behind the same response shape.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query

from domain.classification import Classification
from domain.feedback import Feedback, FeedbackChannel, Platform
from entrypoints.web_api.dependencies import (
    classification_repository,
    feedback_repository,
)
from entrypoints.web_api.schemas.analytics_schema import (
    CategoriesResponse,
    CategoryCount,
    VolumeBucket,
    VolumeResponse,
)
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort

router = APIRouter(prefix="/api", tags=["analytics"])

_MAX_RANGE_DAYS = 90


@router.get("/analytics/volume", response_model=VolumeResponse)
def feedback_volume(
    range_days: int = Query(default=7, ge=1, le=_MAX_RANGE_DAYS),
    app: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
) -> VolumeResponse:
    platform_filter = _coerce_platform(platform)
    channel_filter = _coerce_channel(channel)
    since = datetime.now(timezone.utc) - timedelta(days=range_days)

    feedbacks = list(
        feedback_repo.list_by_filters(
            app_slug=app,
            platform=platform_filter,
            channel=channel_filter,
            since=since,
        )
    )

    buckets: dict = {}
    for feedback in feedbacks:
        day = feedback.received_at.date()
        bucket = buckets.setdefault(
            day,
            {
                "total": 0,
                "by_channel": Counter(),
                "by_platform": Counter(),
                "by_app": Counter(),
            },
        )
        bucket["total"] += 1
        bucket["by_channel"][feedback.channel.value] += 1
        bucket["by_platform"][feedback.platform.value] += 1
        bucket["by_app"][feedback.app_slug] += 1

    response_buckets = [
        VolumeBucket(
            bucket_date=day,
            total=data["total"],
            by_channel=dict(data["by_channel"]),
            by_platform=dict(data["by_platform"]),
            by_app=dict(data["by_app"]),
        )
        for day, data in sorted(buckets.items())
    ]
    return VolumeResponse(range_days=range_days, buckets=response_buckets)


@router.get("/analytics/categories", response_model=CategoriesResponse)
def category_mix(
    range_days: int = Query(default=7, ge=1, le=_MAX_RANGE_DAYS),
    app: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
    classification_repo: ClassificationRepositoryPort = Depends(
        classification_repository
    ),
) -> CategoriesResponse:
    platform_filter = _coerce_platform(platform)
    channel_filter = _coerce_channel(channel)
    since = datetime.now(timezone.utc) - timedelta(days=range_days)

    feedbacks: Iterable[Feedback] = feedback_repo.list_by_filters(
        app_slug=app,
        platform=platform_filter,
        channel=channel_filter,
        since=since,
    )

    counts: defaultdict = defaultdict(
        lambda: {
            "count": 0,
            "severity": Counter(),
            "sentiment": Counter(),
        }
    )
    classified_total = 0
    for feedback in feedbacks:
        classification: Classification | None = classification_repo.get(feedback.id)
        if classification is None:
            continue
        classified_total += 1
        key = (classification.category.value, classification.sub_category)
        entry = counts[key]
        entry["count"] += 1
        entry["severity"][classification.severity.value] += 1
        entry["sentiment"][classification.sentiment.value] += 1

    category_rows = [
        CategoryCount(
            category=category,
            sub_category=sub_category,
            count=data["count"],
            severity_breakdown=dict(data["severity"]),
            sentiment_breakdown=dict(data["sentiment"]),
        )
        for (category, sub_category), data in sorted(
            counts.items(), key=lambda item: item[1]["count"], reverse=True
        )
    ]
    return CategoriesResponse(
        range_days=range_days,
        total_classified_feedback=classified_total,
        categories=category_rows,
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
