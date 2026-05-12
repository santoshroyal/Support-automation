"""In-memory AuditLogRepository tests."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from adapters.persistence.in_memory_audit_log_repository import (
    InMemoryAuditLogRepository,
)
from domain.audit_log import AuditLogEntry


def _entry(
    actor: str = "draft-replies",
    action: str = "draft-replies.started",
    occurred_at: datetime | None = None,
) -> AuditLogEntry:
    return AuditLogEntry(
        actor=actor,
        action=action,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )


def test_added_entries_show_in_list_recent_newest_first():
    repo = InMemoryAuditLogRepository()
    now = datetime.now(timezone.utc)

    older = _entry(occurred_at=now - timedelta(hours=2))
    newer = _entry(occurred_at=now - timedelta(minutes=5))
    repo.add(older)
    repo.add(newer)

    rows = list(repo.list_recent())
    assert [r.id for r in rows] == [newer.id, older.id]


def test_since_filter_drops_older_entries():
    repo = InMemoryAuditLogRepository()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)

    repo.add(_entry(occurred_at=now - timedelta(hours=2)))  # before cutoff
    inside = _entry(occurred_at=now - timedelta(minutes=10))  # after cutoff
    repo.add(inside)

    rows = list(repo.list_recent(since=cutoff))
    assert [r.id for r in rows] == [inside.id]


def test_actor_filter_narrows_to_one_cron():
    repo = InMemoryAuditLogRepository()
    repo.add(_entry(actor="draft-replies"))
    repo.add(_entry(actor="ingest-feedback"))
    repo.add(_entry(actor="draft-replies"))

    rows = list(repo.list_recent(actor="draft-replies"))
    assert len(rows) == 2
    assert all(row.actor == "draft-replies" for row in rows)


def test_limit_caps_result_count():
    repo = InMemoryAuditLogRepository()
    for _ in range(5):
        repo.add(_entry())

    rows = list(repo.list_recent(limit=2))
    assert len(rows) == 2


def test_details_round_trip_through_storage():
    repo = InMemoryAuditLogRepository()
    feedback_id = uuid4()
    repo.add(
        AuditLogEntry(
            actor="draft-replies",
            action="draft.delivered",
            entity_type="Feedback",
            entity_id=feedback_id,
            details={"language_model": "claude_code", "citation_count": 3},
        )
    )
    rows = list(repo.list_recent())
    assert rows[0].entity_id == feedback_id
    assert rows[0].details == {"language_model": "claude_code", "citation_count": 3}
