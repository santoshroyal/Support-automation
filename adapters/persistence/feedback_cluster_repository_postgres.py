"""PostgreSQL-backed FeedbackClusterRepository, using pgvector for similarity search.

Find-or-create flow:
  1. Run a vector similarity query against feedback_cluster.embedding_centroid,
     ordered by cosine distance ascending. The closest match is the candidate.
  2. If 1 - distance ≥ similarity_threshold, return that cluster.
  3. Otherwise create a new cluster with the incoming embedding as its centroid.

Cluster volumes (powers spike detection):
  Per-cluster aggregation that returns, for a rolling recent window and a
  longer baseline window, (count_in_recent, daily_baseline_average) plus
  a small sample of feedback_ids for the alert. Built on the
  feedback_cluster_membership table whose `received_at` column is
  denormalised so this query never has to join feedback.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID, uuid4

from sqlalchemy import case, func, select

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import (
    FeedbackClusterMembershipOrm,
    FeedbackClusterOrm,
)
from domain.feedback_cluster import ClusterMembership, FeedbackCluster
from service_layer.ports.feedback_cluster_repository_port import ClusterVolume


class FeedbackClusterRepositoryPostgres:
    def find_or_create_cluster_for(
        self,
        embedding: list[float],
        similarity_threshold: float,
        seed_label: str | None = None,
    ) -> tuple[FeedbackCluster, bool]:
        with session_scope() as session:
            statement = (
                select(
                    FeedbackClusterOrm,
                    FeedbackClusterOrm.embedding_centroid.cosine_distance(
                        embedding
                    ).label("distance"),
                )
                .order_by(FeedbackClusterOrm.embedding_centroid.cosine_distance(embedding))
                .limit(1)
            )
            row = session.execute(statement).first()
            if row is not None:
                cluster_orm, distance = row
                similarity = 1.0 - float(distance)
                if similarity >= similarity_threshold:
                    return _to_domain(cluster_orm), False

            now = datetime.now(timezone.utc)
            new_orm = FeedbackClusterOrm(
                id=uuid4(),
                label=seed_label,
                embedding_centroid=list(embedding),
                member_count=0,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(new_orm)
            session.flush()
            return _to_domain(new_orm), True

    def add_membership(self, membership: ClusterMembership) -> None:
        if membership.received_at is None:
            raise ValueError(
                "ClusterMembership.received_at is required for the Postgres repo "
                "(used by the spike-volume query)."
            )
        with session_scope() as session:
            already = session.execute(
                select(FeedbackClusterMembershipOrm.feedback_id).where(
                    FeedbackClusterMembershipOrm.feedback_id == membership.feedback_id
                )
            ).first()
            if already is not None:
                return

            cluster_orm = session.get(FeedbackClusterOrm, membership.cluster_id)
            if cluster_orm is None:
                return

            session.add(
                FeedbackClusterMembershipOrm(
                    feedback_id=membership.feedback_id,
                    cluster_id=membership.cluster_id,
                    similarity=membership.similarity,
                    received_at=_ensure_utc(membership.received_at),
                )
            )

            cluster_orm.member_count = cluster_orm.member_count + 1
            cluster_orm.last_seen_at = datetime.now(timezone.utc)
            # NOTE: centroid running-mean update is deliberately deferred until
            # we promote the embedding to the membership row. For phase 1 the
            # centroid stays at the first member's embedding, which is good
            # enough for fixture volumes; the cluster-quality polish follow-up
            # adds proper running-mean updates.

    def has_membership_for(self, feedback_id: UUID) -> bool:
        with session_scope() as session:
            return (
                session.execute(
                    select(FeedbackClusterMembershipOrm.feedback_id).where(
                        FeedbackClusterMembershipOrm.feedback_id == feedback_id
                    )
                ).first()
                is not None
            )

    def list_clusters(self) -> Iterable[FeedbackCluster]:
        with session_scope() as session:
            return [
                _to_domain(row)
                for row in session.execute(select(FeedbackClusterOrm)).scalars()
            ]

    def get_cluster(self, cluster_id: UUID) -> FeedbackCluster | None:
        with session_scope() as session:
            row = session.get(FeedbackClusterOrm, cluster_id)
            return _to_domain(row) if row else None

    def list_members(self, cluster_id: UUID) -> Iterable[UUID]:
        with session_scope() as session:
            statement = select(FeedbackClusterMembershipOrm.feedback_id).where(
                FeedbackClusterMembershipOrm.cluster_id == cluster_id
            )
            return [row for row in session.execute(statement).scalars()]

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

        with session_scope() as session:
            # Aggregate per-cluster counts in two time windows in one query.
            recent_count = func.count(
                case(
                    (FeedbackClusterMembershipOrm.received_at >= recent_cutoff, 1),
                    else_=None,
                )
            )
            baseline_count = func.count(
                case(
                    (
                        (FeedbackClusterMembershipOrm.received_at >= baseline_start)
                        & (FeedbackClusterMembershipOrm.received_at < baseline_end),
                        1,
                    ),
                    else_=None,
                )
            )
            counts_statement = (
                select(
                    FeedbackClusterMembershipOrm.cluster_id,
                    recent_count.label("recent_count"),
                    baseline_count.label("baseline_count"),
                )
                .group_by(FeedbackClusterMembershipOrm.cluster_id)
            )
            rows = session.execute(counts_statement).all()
            volumes: list[ClusterVolume] = []
            for cluster_id, recent, baseline in rows:
                # Pull a small sample of recent feedback ids per cluster.
                samples_statement = (
                    select(FeedbackClusterMembershipOrm.feedback_id)
                    .where(
                        FeedbackClusterMembershipOrm.cluster_id == cluster_id,
                        FeedbackClusterMembershipOrm.received_at >= recent_cutoff,
                    )
                    .order_by(FeedbackClusterMembershipOrm.received_at.desc())
                    .limit(sample_size)
                )
                sample_ids = tuple(session.execute(samples_statement).scalars())
                volumes.append(
                    ClusterVolume(
                        cluster_id=cluster_id,
                        last_window_count=int(recent),
                        daily_baseline=float(baseline) / baseline_window_days,
                        sample_feedback_ids=sample_ids,
                    )
                )
            return volumes


def _to_domain(row: FeedbackClusterOrm) -> FeedbackCluster:
    return FeedbackCluster(
        id=row.id,
        label=row.label,
        embedding_centroid=list(row.embedding_centroid),
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        member_count=row.member_count,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
