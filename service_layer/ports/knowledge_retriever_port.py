"""Port for RAG retrieval over the knowledge base.

Hides chunking, vector + lexical search, RRF, and reranking from use cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol
from uuid import UUID


@dataclass(frozen=True)
class RetrievedChunk:
    knowledge_chunk_id: UUID
    knowledge_document_id: UUID
    content: str
    source_url: str | None
    source_title: str
    score: float


class KnowledgeRetrieverPort(Protocol):
    def retrieve(self, query_text: str, top_k: int = 8) -> Iterable[RetrievedChunk]: ...
