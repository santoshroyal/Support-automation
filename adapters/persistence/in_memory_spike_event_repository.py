"""In-memory SpikeEventRepository — used during local dev and tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

from domain.spike_event import SpikeEvent


class InMemorySpikeEventRepository:
    def __init__(self) -> None:
        self._events: list[SpikeEvent] = []

    def add(self, event: SpikeEvent) -> None:
        self._events.append(event)

    def has_recent_event_for(self, cluster_id: UUID, within_seconds: int) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
        return any(
            event.cluster_id == cluster_id and event.window_end >= cutoff
            for event in self._events
        )

    def list_recent(self, since: datetime) -> Iterable[SpikeEvent]:
        return [event for event in self._events if event.window_end >= since]

    def __len__(self) -> int:
        return len(self._events)
