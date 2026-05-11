"""In-memory FeedbackClusterRepository — used during local dev and tests.

Cosine similarity is computed in pure Python; with at most a few hundred
clusters in memory the linear scan is fine. The Postgres-backed sibling
uses pgvector's HNSW index for the same operation against thousands of
clusters at production scale.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

from domain.feedback_cluster import ClusterMembership, FeedbackCluster
from service_layer.ports.feedback_cluster_repository_port import ClusterVolume


class InMemoryFeedbackClusterRepository:
    def __init__(self) -> None:
        self._clusters: dict[UUID, FeedbackCluster] = {}
        # cluster_id → list of (feedback_id, received_at) tuples
        self._members: dict[UUID, list[tuple[UUID, datetime | None]]] = {}
        # feedback_id → cluster_id (for fast `has_membership_for`)
        self._membership_index: dict[UUID, UUID] = {}

    def find_or_create_cluster_for(
        self,
        embedding: list[float],
        similarity_threshold: float,
        seed_label: str | None = None,
    ) -> tuple[FeedbackCluster, bool]:
        best_cluster: FeedbackCluster | None = None
        best_similarity = -1.0
        for cluster in self._clusters.values():
            similarity = _cosine_similarity(cluster.embedding_centroid, embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster

        if best_cluster is not None and best_similarity >= similarity_threshold:
            return best_cluster, False

        now = datetime.now(timezone.utc)
        new_cluster = FeedbackCluster(
            embedding_centroid=list(embedding),
            label=seed_label,
            first_seen_at=now,
            last_seen_at=now,
            member_count=0,
        )
        self._clusters[new_cluster.id] = new_cluster
        self._members[new_cluster.id] = []
        return new_cluster, True

    def add_membership(self, membership: ClusterMembership) -> None:
        cluster = self._clusters.get(membership.cluster_id)
        if cluster is None:
            return
        if membership.feedback_id in self._membership_index:
            return  # already a member
        self._members[cluster.id].append((membership.feedback_id, membership.received_at))
        self._membership_index[membership.feedback_id] = cluster.id
        cluster.member_count += 1
        cluster.last_seen_at = datetime.now(timezone.utc)

    def has_membership_for(self, feedback_id: UUID) -> bool:
        return feedback_id in self._membership_index

    def list_clusters(self) -> Iterable[FeedbackCluster]:
        return list(self._clusters.values())

    def get_cluster(self, cluster_id: UUID) -> FeedbackCluster | None:
        return self._clusters.get(cluster_id)

    def list_members(self, cluster_id: UUID) -> Iterable[UUID]:
        return [feedback_id for feedback_id, _ in self._members.get(cluster_id, [])]

    def cluster_volumes(
        self,
        recent_window_hours: int,
        baseline_window_days: int,
        sample_size: int = 5,
    ) -> Iterable[ClusterVolume]:
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(hours=recent_window_hours)
        baseline_start = now - timedelta(days=baseline_window_days + 1)
        baseline_end = now - timedelta(days=1)

        results: list[ClusterVolume] = []
        for cluster_id, members in self._members.items():
            recent: list[UUID] = []
            baseline_count = 0
            for feedback_id, received_at in members:
                if received_at is None:
                    continue
                if received_at >= recent_cutoff:
                    recent.append(feedback_id)
                elif baseline_start <= received_at < baseline_end:
                    baseline_count += 1
            results.append(
                ClusterVolume(
                    cluster_id=cluster_id,
                    last_window_count=len(recent),
                    daily_baseline=baseline_count / baseline_window_days,
                    sample_feedback_ids=tuple(recent[:sample_size]),
                )
            )
        return results


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)
