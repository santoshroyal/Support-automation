"""Port for managing feedback clusters and their memberships.

The clustering use case asks the repository to find an existing cluster
whose centroid is close enough to a given embedding, or to create a new
cluster if no match exists. Cluster centroids are running means of
member embeddings; the repository is responsible for keeping them up to
date as new members join.

Spike detection also depends on this port — specifically on
`cluster_volumes()` which returns, per cluster, a recent-window count
and a baseline daily average. That join (feedback × membership × time
windows) lives here because the result is keyed by cluster and aggregates
membership rows; the spike use case stays agnostic of SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol
from uuid import UUID

from domain.feedback_cluster import ClusterMembership, FeedbackCluster


@dataclass(frozen=True)
class ClusterVolume:
    cluster_id: UUID
    last_window_count: int
    daily_baseline: float
    sample_feedback_ids: tuple[UUID, ...]


class FeedbackClusterRepositoryPort(Protocol):
    def find_or_create_cluster_for(
        self,
        embedding: list[float],
        similarity_threshold: float,
        seed_label: str | None = None,
    ) -> tuple[FeedbackCluster, bool]:
        """Find the closest existing cluster (cosine similarity ≥ threshold)
        or create a new one with `embedding` as its first centroid.

        Returns (cluster, was_created). `was_created=True` lets the caller
        log a "new cluster" audit entry.
        """
        ...

    def add_membership(self, membership: ClusterMembership) -> None:
        """Persist a (feedback_id, cluster_id, similarity) tuple and update
        the cluster's centroid (running mean) and member_count.
        """
        ...

    def has_membership_for(self, feedback_id: UUID) -> bool:
        """True if this feedback has already been clustered."""
        ...

    def list_clusters(self) -> Iterable[FeedbackCluster]:
        """Used by the dashboard's spikes view and by analysts."""
        ...

    def get_cluster(self, cluster_id: UUID) -> FeedbackCluster | None: ...

    def list_members(self, cluster_id: UUID) -> Iterable[UUID]:
        """Yield feedback_ids belonging to this cluster — drives drill-down."""
        ...

    def cluster_volumes(
        self,
        recent_window_hours: int,
        baseline_window_days: int,
        sample_size: int = 5,
    ) -> Iterable[ClusterVolume]:
        """For every active cluster, return the recent window count and the
        daily baseline (mean count per day over the prior `baseline_window_days`).

        `recent_window_hours` is typically 24; `baseline_window_days` typically 7.
        `sample_size` controls how many feedback_ids are attached per cluster
        for the spike alert ("here's what people are saying").
        """
        ...
