"""ClusterFeedback — for each feedback that has a classification but no
cluster membership, embed it and assign it to the closest existing cluster
(or create a new one if no cluster is close enough).

Why we cluster AFTER classification: classification provides the signal a
human cares about (category, severity, sentiment), while clustering provides
the signal spike detection cares about (which feedbacks are saying the
same thing). The two signals are independent — the classifier doesn't
need an embedding, the clusterer doesn't need a category — so each runs
as its own narrow step.

Similarity threshold default of 0.85 is conservative: with multilingual-e5
embeddings, 0.85 cosine roughly corresponds to "same complaint, possibly
across languages." Tuning sits with the operator (future setting).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domain.feedback import Feedback
from domain.feedback_cluster import ClusterMembership
from service_layer.ports.embedding_model_port import EmbeddingModelPort
from service_layer.ports.feedback_cluster_repository_port import (
    FeedbackClusterRepositoryPort,
)
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort


@dataclass(frozen=True)
class ClusterFeedbackResult:
    clustered: int
    new_clusters: int
    skipped_already_clustered: int


class ClusterFeedback:
    def __init__(
        self,
        feedback_repository: FeedbackRepositoryPort,
        cluster_repository: FeedbackClusterRepositoryPort,
        embedding_model: EmbeddingModelPort,
        similarity_threshold: float = 0.85,
    ) -> None:
        self._feedback_repository = feedback_repository
        self._cluster_repository = cluster_repository
        self._embedding_model = embedding_model
        self._similarity_threshold = similarity_threshold

    def run(
        self,
        feedbacks: Iterable[Feedback] | None = None,
        app_slug: str | None = None,
        limit: int = 200,
    ) -> ClusterFeedbackResult:
        clustered = 0
        new_clusters = 0
        skipped = 0

        candidates = (
            list(feedbacks)
            if feedbacks is not None
            else list(
                self._feedback_repository.list_by_filters(app_slug=app_slug, since=None)
            )[:limit]
        )

        for feedback in candidates:
            if self._cluster_repository.has_membership_for(feedback.id):
                skipped += 1
                continue

            embedding = self._embedding_model.embed(feedback.raw_text)
            cluster, was_created = self._cluster_repository.find_or_create_cluster_for(
                embedding=embedding,
                similarity_threshold=self._similarity_threshold,
                seed_label=self._suggest_label(feedback),
            )
            similarity = 1.0 if was_created else self._similarity_threshold
            self._cluster_repository.add_membership(
                ClusterMembership(
                    feedback_id=feedback.id,
                    cluster_id=cluster.id,
                    similarity=similarity,
                    received_at=feedback.received_at,
                )
            )

            clustered += 1
            if was_created:
                new_clusters += 1

        return ClusterFeedbackResult(
            clustered=clustered,
            new_clusters=new_clusters,
            skipped_already_clustered=skipped,
        )

    @staticmethod
    def _suggest_label(feedback: Feedback) -> str:
        """Pre-fill cluster.label from a short prefix of the feedback text.

        Operators can rename labels later (in phase 2 when we add the
        cluster-edit screen). Phase 1 just gives them a hint of what's in
        the cluster so the dashboard isn't full of bare UUIDs.
        """
        text = (feedback.raw_text or "").strip()
        if len(text) <= 80:
            return text
        return text[:77] + "..."
