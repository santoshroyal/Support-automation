"""DraftReply — generated reply awaiting human review/send.

The system never sends on its own in phase 1. A draft moves through:
draft → (sent | edited | rejected | regenerated). The full lifecycle is
recorded so we can later learn from human edits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DraftStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    EDITED = "edited"
    REJECTED = "rejected"
    REGENERATED = "regenerated"


@dataclass
class Citation:
    """Where a claim in the draft came from. Surfaced to support staff for verification."""

    knowledge_chunk_id: UUID
    source_url: str | None
    source_title: str
    snippet: str


@dataclass
class DraftReply:
    feedback_id: UUID
    language_code: str
    body: str
    citations: list[Citation] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    status: DraftStatus = DraftStatus.DRAFT
    generated_at: datetime = field(default_factory=_now)
    sent_at: datetime | None = None
    edited_body: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
