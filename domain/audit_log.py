"""AuditLogEntry — a record of one thing the system did.

Cron entry-points and (eventually) API routes write entries on lifecycle
events: "this cron started", "this cron finished with these counts",
"this draft was sent." Use cases never write audit entries themselves —
the recording happens at the outermost ring, where lifecycle boundaries
are naturally observable. That keeps the domain pure and makes audit
log a swappable / disable-able concern.

`details` is intentionally a free-form dict so each call site can
include the metadata it cares about (counts, fix versions, recipients)
without driving schema migrations. The dashboard renders it as a
key-value pair list; querying it server-side is out of scope for phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AuditLogEntry:
    actor: str
    """Who or what performed the action.

    Conventions:
      - cron job names: "ingest-feedback", "classify-and-cluster",
        "sync-knowledge-base", "draft-replies", "detect-spikes",
        "send-digest"
      - API surface: "api"
      - System startup / migrations: "system"
    """

    action: str
    """What happened. Stable strings the dashboard can group by.

    Common shapes:
      - "<cron>.started"
      - "<cron>.finished"
      - "<cron>.failed"
      - "<entity>.<verb>" — e.g. "draft.delivered", "spike.detected"
    """

    entity_type: str | None = None
    """Domain entity the action concerned, if any: "Feedback", "Draft",
    "Spike", "Digest", or None for pure lifecycle events."""

    entity_id: UUID | None = None
    """Stable identifier of the entity above, if there is one."""

    details: dict[str, Any] = field(default_factory=dict)
    """Free-form context: result counts, error message, fix version,
    recipient list. Rendered as key/value pairs in the dashboard."""

    id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)
