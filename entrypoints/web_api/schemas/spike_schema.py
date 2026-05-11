"""Spike-endpoint response schemas.

A spike is the system's "something happened, look at this" signal:
within some time window, a cluster of similar complaints crossed a
volume threshold relative to its own baseline.

`SpikeSummary` is the row a dashboard list renders. `SpikeDetail` is the
single-spike view: same content plus the cluster label, full sample
feedback ids, and (when present) the sample feedback summaries themselves.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.feedback_cluster import FeedbackCluster
from domain.spike_event import SpikeEvent
from entrypoints.web_api.schemas.feedback_schema import FeedbackSummary


class SpikeSummary(BaseModel):
    id: UUID
    cluster_id: UUID
    cluster_label: str | None = None
    window_start: datetime
    window_end: datetime
    count: int
    baseline: float
    ratio: float
    sample_feedback_ids: list[UUID] = Field(default_factory=list)
    alerted_at: datetime | None = None
    is_active: bool = Field(
        description="True when the spike window ended within the last 24 hours"
    )

    @classmethod
    def from_domain(
        cls,
        event: SpikeEvent,
        cluster: FeedbackCluster | None,
        *,
        is_active: bool,
    ) -> "SpikeSummary":
        return cls(
            id=event.id,
            cluster_id=event.cluster_id,
            cluster_label=cluster.label if cluster else None,
            window_start=event.window_start,
            window_end=event.window_end,
            count=event.count,
            baseline=event.baseline,
            ratio=event.ratio,
            sample_feedback_ids=list(event.sample_feedback_ids),
            alerted_at=event.alerted_at,
            is_active=is_active,
        )


class SpikeDetail(SpikeSummary):
    """Same shape as the summary today — kept distinct so future fields
    (e.g. linked draft IDs, related spikes) can land on the detail view
    only without bloating list payloads."""


class SpikeFeedbacksResponse(BaseModel):
    spike_id: UUID
    cluster_id: UUID
    feedbacks: list[FeedbackSummary] = Field(default_factory=list)
