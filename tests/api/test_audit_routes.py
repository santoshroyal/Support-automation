"""Audit endpoint tests — list + filter + limit."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from adapters.persistence.in_memory_audit_log_repository import (
    InMemoryAuditLogRepository,
)
from domain.audit_log import AuditLogEntry
from entrypoints.composition_root import reset_app_for_tests
from entrypoints.web_api.dependencies import audit_log_repository
from entrypoints.web_api.main import create_app


@pytest.fixture
def seeded_repo():
    repo = InMemoryAuditLogRepository()
    now = datetime.now(timezone.utc)

    repo.add(
        AuditLogEntry(
            actor="draft-replies",
            action="draft-replies.started",
            occurred_at=now - timedelta(minutes=10),
        )
    )
    repo.add(
        AuditLogEntry(
            actor="draft-replies",
            action="draft-replies.finished",
            details={"drafted": 3, "skipped": 8},
            occurred_at=now - timedelta(minutes=8),
        )
    )
    repo.add(
        AuditLogEntry(
            actor="ingest-feedback",
            action="ingest-feedback.finished",
            details={"new_rows": 12},
            occurred_at=now - timedelta(days=2),
        )
    )
    return repo


def _client(repo):
    reset_app_for_tests()
    app = create_app()
    app.dependency_overrides[audit_log_repository] = lambda: repo
    return TestClient(app)


def test_list_returns_all_entries_newest_first(seeded_repo):
    client = _client(seeded_repo)

    response = client.get("/api/audit")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 3
    actions = [item["action"] for item in items]
    assert actions[0] == "draft-replies.finished"  # newest
    assert actions[-1] == "ingest-feedback.finished"  # oldest


def test_actor_filter_narrows_to_one_cron(seeded_repo):
    client = _client(seeded_repo)

    response = client.get("/api/audit?actor=draft-replies")

    items = response.json()
    assert len(items) == 2
    assert all(item["actor"] == "draft-replies" for item in items)


def test_since_filter_drops_older_entries(seeded_repo):
    client = _client(seeded_repo)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    # `cutoff` contains a literal `+` from the +00:00 timezone offset, which
    # would be URL-decoded as a space — use `params=` so requests escapes it.
    response = client.get("/api/audit", params={"since": cutoff})

    items = response.json()
    assert len(items) == 2  # the two recent draft-replies rows
    assert all(item["actor"] == "draft-replies" for item in items)


def test_limit_caps_response_size(seeded_repo):
    client = _client(seeded_repo)

    response = client.get("/api/audit?limit=1")

    items = response.json()
    assert len(items) == 1


def test_invalid_limit_rejected(seeded_repo):
    client = _client(seeded_repo)

    response = client.get("/api/audit?limit=99999")

    assert response.status_code == 422


def test_details_round_trip(seeded_repo):
    seeded_repo.add(
        AuditLogEntry(
            actor="send-digest",
            action="send-digest.finished",
            entity_type="Digest",
            entity_id=uuid4(),
            details={"recipients": ["ops@example.com"], "spike_count": 2},
        )
    )
    client = _client(seeded_repo)

    response = client.get("/api/audit?actor=send-digest")

    items = response.json()
    assert items[0]["details"]["recipients"] == ["ops@example.com"]
    assert items[0]["details"]["spike_count"] == 2
