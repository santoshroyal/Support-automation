"""FeedbackCluster — a group of semantically similar feedback items.

The spike detector operates on clusters. A cluster's centroid is the running
mean of member embeddings; the clustering use case maintains it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class FeedbackCluster:
    embedding_centroid: list[float]
    label: str | None = None
    id: UUID = field(default_factory=uuid4)
    first_seen_at: datetime = field(default_factory=_now)
    last_seen_at: datetime = field(default_factory=_now)
    member_count: int = 0


@dataclass(frozen=True)
class ClusterMembership:
    feedback_id: UUID
    cluster_id: UUID
    similarity: float
    # `received_at` is denormalised onto membership rows so the spike-volume
    # query can window by time without joining feedback. Both repositories
    # store it; the Postgres repo could equivalently get it via a join, but
    # the duplication keeps the in-memory implementation viable too.
    received_at: datetime | None = None
