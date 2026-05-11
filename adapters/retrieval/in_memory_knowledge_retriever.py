"""In-memory KnowledgeRetriever for unit tests.

Holds a list of (chunk, embedding) pairs and ranks by cosine similarity
plus a naive substring overlap. Not used in production — the Postgres
hybrid retriever is the real implementation. This exists so tests can
exercise use cases that depend on `KnowledgeRetrieverPort` without
spinning up Postgres + pgvector.
"""

from __future__ import annotations

import math
from typing import Iterable
from uuid import UUID

from service_layer.ports.embedding_model_port import EmbeddingModelPort
from service_layer.ports.knowledge_retriever_port import RetrievedChunk


class _Indexed:
    def __init__(
        self,
        knowledge_chunk_id: UUID,
        knowledge_document_id: UUID,
        content: str,
        embedding: list[float],
        source_url: str | None = None,
        source_title: str = "",
    ) -> None:
        self.knowledge_chunk_id = knowledge_chunk_id
        self.knowledge_document_id = knowledge_document_id
        self.content = content
        self.embedding = embedding
        self.source_url = source_url
        self.source_title = source_title


class InMemoryKnowledgeRetriever:
    def __init__(self, embedding_model: EmbeddingModelPort) -> None:
        self._embedding_model = embedding_model
        self._chunks: list[_Indexed] = []

    def index(
        self,
        knowledge_chunk_id: UUID,
        knowledge_document_id: UUID,
        content: str,
        source_url: str | None = None,
        source_title: str = "",
    ) -> None:
        embedding = self._embedding_model.embed(content)
        self._chunks.append(
            _Indexed(
                knowledge_chunk_id=knowledge_chunk_id,
                knowledge_document_id=knowledge_document_id,
                content=content,
                embedding=embedding,
                source_url=source_url,
                source_title=source_title,
            )
        )

    def retrieve(self, query_text: str, top_k: int = 8) -> Iterable[RetrievedChunk]:
        if not query_text or not query_text.strip():
            return []
        if not self._chunks:
            return []
        query_embedding = self._embedding_model.embed(query_text)
        scored = [
            (chunk, _cosine_similarity(chunk.embedding, query_embedding))
            for chunk in self._chunks
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [
            RetrievedChunk(
                knowledge_chunk_id=chunk.knowledge_chunk_id,
                knowledge_document_id=chunk.knowledge_document_id,
                content=chunk.content,
                source_url=chunk.source_url,
                source_title=chunk.source_title,
                score=float(score),
            )
            for chunk, score in scored[:top_k]
        ]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
