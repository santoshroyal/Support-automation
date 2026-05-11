"""Spike list / detail / drill-down endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from adapters.persistence.in_memory_classification_repository import (
    InMemoryClassificationRepository,
)
from adapters.persistence.in_memory_draft_reply_repository import (
    InMemoryDraftReplyRepository,
)
from adapters.persistence.in_memory_feedback_cluster_repository import (
    InMemoryFeedbackClusterRepository,
)
from adapters.persistence.in_memory_feedback_repository import (
    InMemoryFeedbackRepository,
)
from adapters.persistence.in_memory_spike_event_repository import (
    InMemorySpikeEventRepository,
)
from domain.feedback import Feedback, FeedbackChannel, Platform
from domain.feedback_cluster import FeedbackCluster
from domain.spike_event import SpikeEvent
from entrypoints.composition_root import reset_app_for_tests
from entrypoints.web_api.dependencies import (
    classification_repository,
    cluster_repository,
    draft_reply_repository,
    feedback_repository,
    spike_event_repository,
)
from entrypoints.web_api.main import create_app


@pytest.fixture
def seeded():
    feedback_repo = InMemoryFeedbackRepository()
    classification_repo = InMemoryClassificationRepository()
    draft_repo = InMemoryDraftReplyRepository()
    spike_repo = InMemorySpikeEventRepository()
    cluster_repo = InMemoryFeedbackClusterRepository()

    now = datetime.now(timezone.utc)

    feedback_a = Feedback(
        channel=FeedbackChannel.GOOGLE_PLAY,
        app_slug="et",
        platform=Platform.ANDROID,
        external_id="p1",
        author_identifier="MarketPro123",
        raw_text="Live market data lag.",
        received_at=now - timedelta(hours=2),
        language_code="en",
    )
    feedback_b = Feedback(
        channel=FeedbackChannel.GMAIL,
        app_slug="toi",
        platform=Platform.UNKNOWN,
        external_id="m1",
        author_identifier="user@example.com",
        raw_text="Video crash.",
        received_at=now - timedelta(hours=4),
        language_code="en",
    )
    feedback_repo.add(feedback_a)
    feedback_repo.add(feedback_b)

    # Cluster covering feedback_a (ET app) — only the cluster object is read
    # by the spike endpoints (for `cluster_label`), so member rows are
    # intentionally not seeded.
    et_cluster = FeedbackCluster(
        embedding_centroid=[0.1] * 768, label="ET market data lag"
    )
    cluster_repo._clusters[et_cluster.id] = et_cluster

    # Active spike (within last 24h) for ET
    active_spike = SpikeEvent(
        cluster_id=et_cluster.id,
        window_start=now - timedelta(hours=23),
        window_end=now - timedelta(hours=1),
        count=12,
        baseline=2.0,
        ratio=6.0,
        sample_feedback_ids=[feedback_a.id],
    )
    # Old historical spike (3 days ago) — unrelated cluster
    old_cluster = FeedbackCluster(embedding_centroid=[0.2] * 768, label="Old cluster")
    cluster_repo._clusters[old_cluster.id] = old_cluster
    old_spike = SpikeEvent(
        cluster_id=old_cluster.id,
        window_start=now - timedelta(days=3, hours=2),
        window_end=now - timedelta(days=3),
        count=8,
        baseline=2.0,
        ratio=4.0,
        sample_feedback_ids=[feedback_b.id],
    )
    spike_repo.add(active_spike)
    spike_repo.add(old_spike)

    return {
        "feedback_a": feedback_a,
        "feedback_b": feedback_b,
        "active_spike": active_spike,
        "old_spike": old_spike,
        "et_cluster": et_cluster,
        "feedback_repo": feedback_repo,
        "classification_repo": classification_repo,
        "draft_repo": draft_repo,
        "spike_repo": spike_repo,
        "cluster_repo": cluster_repo,
    }


def _client(seeded):
    reset_app_for_tests()
    app = create_app()
    app.dependency_overrides[feedback_repository] = lambda: seeded["feedback_repo"]
    app.dependency_overrides[classification_repository] = lambda: seeded[
        "classification_repo"
    ]
    app.dependency_overrides[draft_reply_repository] = lambda: seeded["draft_repo"]
    app.dependency_overrides[spike_event_repository] = lambda: seeded["spike_repo"]
    app.dependency_overrides[cluster_repository] = lambda: seeded["cluster_repo"]
    return TestClient(app)


def test_list_returns_both_spikes_newest_first(seeded):
    client = _client(seeded)

    response = client.get("/api/spikes")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert items[0]["id"] == str(seeded["active_spike"].id)
    assert items[0]["is_active"] is True
    assert items[1]["is_active"] is False


def test_list_active_filter_drops_historical(seeded):
    client = _client(seeded)

    response = client.get("/api/spikes?active=true")

    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(seeded["active_spike"].id)


def test_list_inactive_filter_drops_active(seeded):
    client = _client(seeded)

    response = client.get("/api/spikes?active=false")

    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(seeded["old_spike"].id)


def test_list_filter_by_app_keeps_only_matching_spikes(seeded):
    client = _client(seeded)

    response = client.get("/api/spikes?app=et")

    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(seeded["active_spike"].id)


def test_detail_includes_cluster_label(seeded):
    client = _client(seeded)

    response = client.get(f"/api/spikes/{seeded['active_spike'].id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["cluster_label"] == "ET market data lag"
    assert detail["ratio"] == 6.0


def test_detail_404_for_unknown_spike(seeded):
    client = _client(seeded)

    response = client.get(f"/api/spikes/{uuid4()}")

    assert response.status_code == 404


def test_drill_down_returns_sample_feedbacks(seeded):
    client = _client(seeded)

    response = client.get(f"/api/spikes/{seeded['active_spike'].id}/feedbacks")

    assert response.status_code == 200
    body = response.json()
    assert body["spike_id"] == str(seeded["active_spike"].id)
    assert len(body["feedbacks"]) == 1
    assert body["feedbacks"][0]["id"] == str(seeded["feedback_a"].id)
