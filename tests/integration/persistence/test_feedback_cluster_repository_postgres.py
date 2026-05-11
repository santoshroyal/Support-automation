"""FeedbackClusterRepositoryPostgres satisfies the contract using pgvector.

The integration suite uses the same separate test database the other
persistence tests use. We seed deterministic embeddings (not real ones)
so the test asserts behaviour, not embedding quality.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.feedback import Feedback, FeedbackChannel, Platform
from domain.feedback_cluster import ClusterMembership

# Two clearly different unit vectors in 768 dimensions.
_EMBEDDING_A = [1.0] + [0.0] * 767
_EMBEDDING_B = [0.0, 1.0] + [0.0] * 766
# Very close to A — should cluster with A under any sensible threshold.
_EMBEDDING_A_SHIFTED = [0.99, 0.01] + [0.0] * 766


@pytest.fixture
def repos(clean_tables):
    from adapters.persistence.feedback_cluster_repository_postgres import (
        FeedbackClusterRepositoryPostgres,
    )
    from adapters.persistence.feedback_repository_postgres import (
        FeedbackRepositoryPostgres,
    )

    return FeedbackRepositoryPostgres(), FeedbackClusterRepositoryPostgres()


def _seed_feedback(repo, external_id: str = None) -> Feedback:
    feedback = Feedback(
        channel=FeedbackChannel.GMAIL,
        app_slug="toi",
        platform=Platform.UNKNOWN,
        external_id=external_id or f"id_{uuid4().hex[:8]}",
        author_identifier="x@example.com",
        raw_text="anything",
        received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
    )
    repo.add(feedback)
    return feedback


def test_first_call_creates_a_cluster(repos):
    feedback_repo, cluster_repo = repos
    feedback = _seed_feedback(feedback_repo)

    cluster, was_created = cluster_repo.find_or_create_cluster_for(
        embedding=_EMBEDDING_A,
        similarity_threshold=0.85,
        seed_label="first cluster",
    )
    assert was_created is True
    assert cluster.label == "first cluster"

    cluster_repo.add_membership(
        ClusterMembership(
            feedback_id=feedback.id,
            cluster_id=cluster.id,
            similarity=1.0,
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )
    assert cluster_repo.has_membership_for(feedback.id) is True


def test_close_embedding_joins_existing_cluster(repos):
    feedback_repo, cluster_repo = repos
    a = _seed_feedback(feedback_repo)
    b = _seed_feedback(feedback_repo)

    cluster_a, created_a = cluster_repo.find_or_create_cluster_for(
        embedding=_EMBEDDING_A, similarity_threshold=0.85
    )
    cluster_repo.add_membership(
        ClusterMembership(
            feedback_id=a.id,
            cluster_id=cluster_a.id,
            similarity=1.0,
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )

    cluster_b, created_b = cluster_repo.find_or_create_cluster_for(
        embedding=_EMBEDDING_A_SHIFTED, similarity_threshold=0.85
    )

    assert created_a is True
    assert created_b is False
    assert cluster_b.id == cluster_a.id


def test_distant_embedding_creates_new_cluster(repos):
    feedback_repo, cluster_repo = repos
    a = _seed_feedback(feedback_repo)

    cluster_a, _ = cluster_repo.find_or_create_cluster_for(
        embedding=_EMBEDDING_A, similarity_threshold=0.85
    )
    cluster_repo.add_membership(
        ClusterMembership(
            feedback_id=a.id,
            cluster_id=cluster_a.id,
            similarity=1.0,
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )

    _, created_b = cluster_repo.find_or_create_cluster_for(
        embedding=_EMBEDDING_B, similarity_threshold=0.85
    )

    assert created_b is True
    clusters = list(cluster_repo.list_clusters())
    assert len(clusters) == 2


def test_member_count_increments(repos):
    feedback_repo, cluster_repo = repos
    a = _seed_feedback(feedback_repo)
    b = _seed_feedback(feedback_repo)

    cluster, _ = cluster_repo.find_or_create_cluster_for(
        embedding=_EMBEDDING_A, similarity_threshold=0.85
    )
    cluster_repo.add_membership(
        ClusterMembership(
            feedback_id=a.id,
            cluster_id=cluster.id,
            similarity=1.0,
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )
    cluster_repo.add_membership(
        ClusterMembership(
            feedback_id=b.id,
            cluster_id=cluster.id,
            similarity=0.95,
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )

    refreshed = cluster_repo.get_cluster(cluster.id)
    assert refreshed.member_count == 2


def test_list_members_returns_all_feedback_ids(repos):
    feedback_repo, cluster_repo = repos
    a = _seed_feedback(feedback_repo)
    b = _seed_feedback(feedback_repo)

    cluster, _ = cluster_repo.find_or_create_cluster_for(
        embedding=_EMBEDDING_A, similarity_threshold=0.85
    )
    cluster_repo.add_membership(
        ClusterMembership(
            feedback_id=a.id,
            cluster_id=cluster.id,
            similarity=1.0,
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )
    cluster_repo.add_membership(
        ClusterMembership(
            feedback_id=b.id,
            cluster_id=cluster.id,
            similarity=0.95,
            received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )

    members = set(cluster_repo.list_members(cluster.id))
    assert members == {a.id, b.id}
