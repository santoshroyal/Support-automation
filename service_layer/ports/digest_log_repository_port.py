"""Port for recording every digest the system has built (or attempted)."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol
from uuid import UUID, uuid4


class DigestLogEntry:
    """Lightweight record of one digest run."""

    def __init__(
        self,
        type: str,
        body_html: str,
        recipients: list[str],
        sent_at: datetime,
        error: str | None = None,
        id: UUID | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.type = type
        self.body_html = body_html
        self.recipients = recipients
        self.sent_at = sent_at
        self.error = error


class DigestLogRepositoryPort(Protocol):
    def add(self, entry: DigestLogEntry) -> None: ...

    def list_recent(self, since: datetime) -> Iterable[DigestLogEntry]: ...
