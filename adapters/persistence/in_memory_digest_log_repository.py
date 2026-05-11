"""In-memory DigestLogRepository — used during local dev and tests."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from service_layer.ports.digest_log_repository_port import DigestLogEntry


class InMemoryDigestLogRepository:
    def __init__(self) -> None:
        self._entries: list[DigestLogEntry] = []

    def add(self, entry: DigestLogEntry) -> None:
        self._entries.append(entry)

    def list_recent(self, since: datetime) -> Iterable[DigestLogEntry]:
        return [entry for entry in self._entries if entry.sent_at >= since]

    def __len__(self) -> int:
        return len(self._entries)
