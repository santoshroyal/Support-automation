"""Port for persisting audit log entries.

Writers are cron entry-points and the API layer; the dashboard reads
through `list_recent`. The repository is append-only — entries are
never updated or deleted (audit trails that can be edited aren't
audit trails).
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol

from domain.audit_log import AuditLogEntry


class AuditLogRepositoryPort(Protocol):
    def add(self, entry: AuditLogEntry) -> None: ...

    def list_recent(
        self,
        since: datetime | None = None,
        actor: str | None = None,
        limit: int = 200,
    ) -> Iterable[AuditLogEntry]:
        """Newest entries first. Filter by `since` to bound the scan;
        filter by `actor` to narrow to one cron job's history."""
        ...
