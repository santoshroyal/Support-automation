"""SyncKnowledgeBase — pull updated docs from each KnowledgeSource, chunk, embed, persist.

Per source, per cron tick:
  1. Ask the source for documents updated since the last sync (cursor TBD;
     phase 1 just refreshes everything every run, which is fine at fixture
     volume — incremental cursoring lands when real adapters arrive).
  2. For each updated document:
       - upsert it into the repository (insert or update by source+source_id)
       - chunk the body using the document chunker
       - embed each chunk with the local sentence-transformer
       - replace the document's chunk set atomically
  3. Report per-source counts so the cron output is meaningful.

The drafter (phase 1d) consumes the chunks via KnowledgeRetrieverPort,
which is a separate concern — this use case only writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import uuid4

from adapters.retrieval.document_chunker import DocumentChunker
from domain.knowledge_document import KnowledgeChunk, KnowledgeSourceKind
from service_layer.ports.embedding_model_port import EmbeddingModelPort
from service_layer.ports.knowledge_repository_port import KnowledgeRepositoryPort
from service_layer.ports.knowledge_source_port import KnowledgeSourcePort


@dataclass(frozen=True)
class SyncSourceResult:
    source: KnowledgeSourceKind
    documents_synced: int
    chunks_written: int


@dataclass(frozen=True)
class SyncKnowledgeBaseResult:
    per_source: tuple[SyncSourceResult, ...]

    @property
    def total_documents(self) -> int:
        return sum(r.documents_synced for r in self.per_source)

    @property
    def total_chunks(self) -> int:
        return sum(r.chunks_written for r in self.per_source)


class SyncKnowledgeBase:
    def __init__(
        self,
        sources: Sequence[KnowledgeSourcePort],
        knowledge_repository: KnowledgeRepositoryPort,
        embedding_model: EmbeddingModelPort,
        chunker: DocumentChunker | None = None,
    ) -> None:
        self._sources = sources
        self._knowledge_repository = knowledge_repository
        self._embedding_model = embedding_model
        self._chunker = chunker or DocumentChunker()

    def run(self, since: datetime | None = None) -> SyncKnowledgeBaseResult:
        results: list[SyncSourceResult] = []
        for source in self._sources:
            documents_synced = 0
            chunks_written = 0
            for document in source.fetch_updated(since):
                document_id = self._knowledge_repository.upsert_document(document)
                chunks = self._build_chunks(document_id, document.raw_body, document)
                self._knowledge_repository.replace_chunks(document_id, chunks)
                documents_synced += 1
                chunks_written += len(chunks)
            results.append(
                SyncSourceResult(
                    source=source.kind,
                    documents_synced=documents_synced,
                    chunks_written=chunks_written,
                )
            )
        return SyncKnowledgeBaseResult(per_source=tuple(results))

    def _build_chunks(
        self, document_id, raw_body: str, document
    ) -> list[KnowledgeChunk]:
        text_chunks = self._chunker.split(raw_body)
        if not text_chunks:
            return []
        embeddings = self._embedding_model.embed_batch(
            chunk.content for chunk in text_chunks
        )
        return [
            KnowledgeChunk(
                id=uuid4(),
                knowledge_document_id=document_id,
                chunk_index=text_chunk.chunk_index,
                content=text_chunk.content,
                embedding=embedding,
                metadata={
                    "source": document.source.value,
                    "source_id": document.source_id,
                    "title": document.title,
                    "source_url": document.source_url,
                    "last_updated_at": document.last_updated_at.isoformat(),
                },
            )
            for text_chunk, embedding in zip(text_chunks, embeddings)
        ]
