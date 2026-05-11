"""Spike endpoints.

  GET /api/spikes                        — recent spikes, optionally filtered
  GET /api/spikes/{spike_id}             — single spike detail
  GET /api/spikes/{spike_id}/feedbacks   — sample feedbacks linked to the spike

`active` filter: a spike whose `window_end` is within the last 24 hours.
The implementation walks the small set of recent spikes in Python — at
phase-1 volumes (single-digit spikes per app per week) the cost is
negligible. If volumes grow, push the filter down to the repository.

The drill-down endpoint returns the `sample_feedback_ids` recorded on the
spike at detection time (5 representative complaints by default), not the
full cluster membership. That keeps the response bounded; full membership
will arrive as `/api/clusters/{cluster_id}/feedbacks` if it's needed later.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from entrypoints.web_api.dependencies import (
    classification_repository,
    cluster_repository,
    draft_reply_repository,
    feedback_repository,
    spike_event_repository,
)
from entrypoints.web_api.schemas.feedback_schema import FeedbackSummary
from entrypoints.web_api.schemas.spike_schema import (
    SpikeDetail,
    SpikeFeedbacksResponse,
    SpikeSummary,
)
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.draft_reply_repository_port import DraftReplyRepositoryPort
from service_layer.ports.feedback_cluster_repository_port import (
    FeedbackClusterRepositoryPort,
)
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort
from service_layer.ports.spike_event_repository_port import SpikeEventRepositoryPort

router = APIRouter(prefix="/api", tags=["spikes"])

_ACTIVE_WINDOW_HOURS = 24
_DEFAULT_LOOKBACK_DAYS = 30


@router.get("/spikes", response_model=list[SpikeSummary])
def list_spikes(
    active: bool | None = Query(
        default=None,
        description="True → only spikes whose window ended within the last 24h",
    ),
    app: str | None = Query(default=None, description="App slug, e.g. 'toi'"),
    since: datetime | None = Query(
        default=None,
        description="ISO-8601. Default: 30 days ago",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    spike_repo: SpikeEventRepositoryPort = Depends(spike_event_repository),
    cluster_repo: FeedbackClusterRepositoryPort = Depends(cluster_repository),
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
) -> list[SpikeSummary]:
    cutoff = since or _default_since()
    now = datetime.now(timezone.utc)
    active_cutoff = now - timedelta(hours=_ACTIVE_WINDOW_HOURS)

    events = list(spike_repo.list_recent(cutoff))
    events.sort(key=lambda e: e.window_end, reverse=True)

    summaries: list[SpikeSummary] = []
    for event in events:
        is_active = event.window_end >= active_cutoff
        if active is True and not is_active:
            continue
        if active is False and is_active:
            continue
        cluster = cluster_repo.get_cluster(event.cluster_id)
        if app is not None and not _spike_belongs_to_app(
            event, feedback_repo, app_slug=app
        ):
            continue
        summaries.append(SpikeSummary.from_domain(event, cluster, is_active=is_active))
        if len(summaries) >= limit:
            break
    return summaries


@router.get("/spikes/{spike_id}", response_model=SpikeDetail)
def get_spike(
    spike_id: UUID,
    spike_repo: SpikeEventRepositoryPort = Depends(spike_event_repository),
    cluster_repo: FeedbackClusterRepositoryPort = Depends(cluster_repository),
) -> SpikeDetail:
    event = spike_repo.get(spike_id)
    if event is None:
        raise HTTPException(status_code=404, detail="spike_not_found")
    cluster = cluster_repo.get_cluster(event.cluster_id)
    is_active = event.window_end >= datetime.now(timezone.utc) - timedelta(
        hours=_ACTIVE_WINDOW_HOURS
    )
    summary = SpikeSummary.from_domain(event, cluster, is_active=is_active)
    return SpikeDetail(**summary.model_dump())


@router.get("/spikes/{spike_id}/feedbacks", response_model=SpikeFeedbacksResponse)
def list_spike_feedbacks(
    spike_id: UUID,
    spike_repo: SpikeEventRepositoryPort = Depends(spike_event_repository),
    feedback_repo: FeedbackRepositoryPort = Depends(feedback_repository),
    classification_repo: ClassificationRepositoryPort = Depends(
        classification_repository
    ),
    draft_repo: DraftReplyRepositoryPort = Depends(draft_reply_repository),
) -> SpikeFeedbacksResponse:
    event = spike_repo.get(spike_id)
    if event is None:
        raise HTTPException(status_code=404, detail="spike_not_found")
    feedbacks: list[FeedbackSummary] = []
    for feedback_id in event.sample_feedback_ids:
        feedback = feedback_repo.get(feedback_id)
        if feedback is None:
            continue
        feedbacks.append(
            FeedbackSummary.from_domain(
                feedback,
                has_classification=classification_repo.has_classification_for(
                    feedback.id
                ),
                has_draft=draft_repo.has_draft_for(feedback.id),
            )
        )
    return SpikeFeedbacksResponse(
        spike_id=event.id,
        cluster_id=event.cluster_id,
        feedbacks=feedbacks,
    )


def _default_since() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=_DEFAULT_LOOKBACK_DAYS)


def _spike_belongs_to_app(
    event,
    feedback_repo: FeedbackRepositoryPort,
    *,
    app_slug: str,
) -> bool:
    """A spike "belongs to" an app when any of its sample feedbacks is from that app.

    Spike events themselves carry no app_slug (they're keyed by cluster);
    looking through the samples is the cheapest check that doesn't require
    enumerating the full cluster.
    """
    for feedback_id in event.sample_feedback_ids:
        feedback = feedback_repo.get(feedback_id)
        if feedback is not None and feedback.app_slug == app_slug:
            return True
    return False
