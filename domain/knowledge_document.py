"""KnowledgeDocument — one page/issue/row from a knowledge source.

`KnowledgeChunk` is a sub-aggregate; documents are split into chunks for
vector + lexical retrieval. The `metadata` on a chunk preserves citation info
so the drafter can attribute each claim back to its source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeSourceKind(str, Enum):
    CONFLUENCE = "confluence"
    JIRA = "jira"
    GOOGLE_SHEETS = "google_sheets"


@dataclass
class KnowledgeDocument:
    source: KnowledgeSourceKind
    source_id: str
    title: str
    raw_body: str
    last_updated_at: datetime
    source_url: str | None = None
    id: UUID = field(default_factory=uuid4)
    fetched_at: datetime = field(default_factory=_now)


@dataclass
class KnowledgeChunk:
    knowledge_document_id: UUID
    chunk_index: int
    content: str
    embedding: list[float]
    id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)
