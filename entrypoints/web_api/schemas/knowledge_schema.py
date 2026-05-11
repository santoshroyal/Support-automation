"""Knowledge-source health response schemas.

Per-source breakdown of what's been ingested into the knowledge base:
how many documents, how fresh the freshest one is, and a freshness
classification the dashboard can render as a coloured badge without
re-implementing the policy.

The freshness window thresholds are intentionally generous in phase 1
(Confluence/JIRA: stale at >12h, very stale at >48h; Sheets: stale at
>2d, very stale at >7d). They reflect how often the corresponding
real-mode adapter is expected to sync, not strict SLAs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class KnowledgeSourceFreshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    VERY_STALE = "very_stale"
    EMPTY = "empty"


class KnowledgeSourceHealth(BaseModel):
    source: str = Field(description="confluence | jira | google_sheets")
    document_count: int
    latest_document_at: datetime | None = None
    freshness: KnowledgeSourceFreshness


class KnowledgeSourcesResponse(BaseModel):
    total_documents: int
    total_chunks: int
    sources: list[KnowledgeSourceHealth] = Field(default_factory=list)
