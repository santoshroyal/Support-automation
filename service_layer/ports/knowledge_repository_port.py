"""Port for persisting knowledge documents and their chunks.

The sync use case calls these methods in this order:
  1. `upsert_document` to insert-or-update one document by (source, source_id),
     returning the stable id assigned to it (re-used on subsequent runs).
  2. `replace_chunks` to atomically swap the chunks of that document with
     the freshly chunked + embedded set — so re-syncing a document doesn't
     leave stale chunks behind from the previous version.

Reads are simple list/get operations, used by the dashboard's KB freshness
view (later in phase 1f) and by the retriever to pull a chunk's parent
document for citation purposes.
"""

from __future__ import annotations

from typing import Iterable, Protocol
from uuid import UUID

from domain.knowledge_document import KnowledgeChunk, KnowledgeDocument, KnowledgeSourceKind


class KnowledgeRepositoryPort(Protocol):
    def upsert_document(self, document: KnowledgeDocument) -> UUID:
        """Insert or update by (source, source_id). Returns the stable doc id."""
        ...

    def replace_chunks(
        self, knowledge_document_id: UUID, chunks: Iterable[KnowledgeChunk]
    ) -> None:
        """Atomically delete the document's existing chunks and insert the new set."""
        ...

    def get_document(self, document_id: UUID) -> KnowledgeDocument | None: ...

    def get_document_by_source(
        self, source: KnowledgeSourceKind, source_id: str
    ) -> KnowledgeDocument | None: ...

    def list_documents(
        self, source: KnowledgeSourceKind | None = None
    ) -> Iterable[KnowledgeDocument]: ...

    def count_chunks(self) -> int:
        """Useful for the health endpoint and for verifying a sync ran."""
        ...
