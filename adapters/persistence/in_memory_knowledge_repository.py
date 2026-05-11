"""In-memory KnowledgeRepository — used during local dev and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from domain.knowledge_document import KnowledgeChunk, KnowledgeDocument, KnowledgeSourceKind


class InMemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._documents: dict[UUID, KnowledgeDocument] = {}
        # (source, source_id) → document_id  (for upsert)
        self._by_source_key: dict[tuple[KnowledgeSourceKind, str], UUID] = {}
        # document_id → list of chunks
        self._chunks: dict[UUID, list[KnowledgeChunk]] = {}

    def upsert_document(self, document: KnowledgeDocument) -> UUID:
        key = (document.source, document.source_id)
        existing_id = self._by_source_key.get(key)
        if existing_id is not None:
            existing = self._documents[existing_id]
            existing.title = document.title
            existing.raw_body = document.raw_body
            existing.source_url = document.source_url
            existing.last_updated_at = document.last_updated_at
            existing.fetched_at = datetime.now(timezone.utc)
            return existing_id

        document.fetched_at = datetime.now(timezone.utc)
        self._documents[document.id] = document
        self._by_source_key[key] = document.id
        self._chunks[document.id] = []
        return document.id

    def replace_chunks(
        self, knowledge_document_id: UUID, chunks: Iterable[KnowledgeChunk]
    ) -> None:
        if knowledge_document_id not in self._documents:
            return
        self._chunks[knowledge_document_id] = list(chunks)

    def get_document(self, document_id: UUID) -> KnowledgeDocument | None:
        return self._documents.get(document_id)

    def get_document_by_source(
        self, source: KnowledgeSourceKind, source_id: str
    ) -> KnowledgeDocument | None:
        document_id = self._by_source_key.get((source, source_id))
        return self._documents.get(document_id) if document_id else None

    def list_documents(
        self, source: KnowledgeSourceKind | None = None
    ) -> Iterable[KnowledgeDocument]:
        if source is None:
            return list(self._documents.values())
        return [doc for doc in self._documents.values() if doc.source is source]

    def count_chunks(self) -> int:
        return sum(len(chunks) for chunks in self._chunks.values())
