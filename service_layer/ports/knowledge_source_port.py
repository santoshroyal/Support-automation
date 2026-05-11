"""Port for inbound knowledge sources (Confluence, JIRA, Sheets)."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol

from domain.knowledge_document import KnowledgeDocument, KnowledgeSourceKind


class KnowledgeSourcePort(Protocol):
    @property
    def kind(self) -> KnowledgeSourceKind: ...

    def fetch_updated(self, since: datetime | None) -> Iterable[KnowledgeDocument]: ...
