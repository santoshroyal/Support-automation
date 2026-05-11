"""Internal row shape shared by VectorIndex + LexicalIndex.

Both indexes return rows in the same shape so the hybrid retriever can
merge them without translating. The shape carries everything the
KnowledgeRetrieverPort.RetrievedChunk needs, plus the per-index rank.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CandidateRow:
    knowledge_chunk_id: UUID
    knowledge_document_id: UUID
    content: str
    source: str
    source_id: str
    source_url: str | None
    source_title: str
    rank: int  # 1-based
    raw_score: float  # cosine_distance for vector; ts_rank for lexical
