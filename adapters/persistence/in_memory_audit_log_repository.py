"""In-memory AuditLogRepository — used during local dev and tests.

Append-only by design; the port has no delete/update method. List is
returned newest-first to match the Postgres adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from domain.audit_log import AuditLogEntry


class InMemoryAuditLogRepository:
    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    def add(self, entry: AuditLogEntry) -> None:
        self._entries.append(entry)

    def list_recent(
        self,
        since: datetime | None = None,
        actor: str | None = None,
        limit: int = 200,
    ) -> Iterable[AuditLogEntry]:
        results = list(self._entries)
        if since is not None:
            results = [e for e in results if e.occurred_at >= since]
        if actor is not None:
            results = [e for e in results if e.actor == actor]
        results.sort(key=lambda e: e.occurred_at, reverse=True)
        return results[:limit]

    def __len__(self) -> int:
        return len(self._entries)
