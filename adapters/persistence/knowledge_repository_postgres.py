"""PostgreSQL-backed KnowledgeRepository.

Document upsert is implemented as `INSERT ... ON CONFLICT (source, source_id)
DO UPDATE` so the sync use case is idempotent — re-syncing the same
Confluence page just refreshes the existing row without creating duplicates.

`replace_chunks` runs in one transaction: delete all existing chunks for
the document, then insert the new set. Concurrent re-syncs of the same
document are serialised by the cron advisory lock at the CLI level.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import KnowledgeChunkOrm, KnowledgeDocumentOrm
from domain.knowledge_document import KnowledgeChunk, KnowledgeDocument, KnowledgeSourceKind


class KnowledgeRepositoryPostgres:
    def upsert_document(self, document: KnowledgeDocument) -> UUID:
        with session_scope() as session:
            now = datetime.now(timezone.utc)
            statement = (
                pg_insert(KnowledgeDocumentOrm)
                .values(
                    id=document.id,
                    source=document.source.value,
                    source_id=document.source_id,
                    title=document.title,
                    source_url=document.source_url,
                    raw_body=document.raw_body,
                    last_updated_at=_ensure_utc(document.last_updated_at),
                    fetched_at=now,
                )
                .on_conflict_do_update(
                    constraint="uq_knowledge_document_source",
                    set_={
                        "title": document.title,
                        "source_url": document.source_url,
                        "raw_body": document.raw_body,
                        "last_updated_at": _ensure_utc(document.last_updated_at),
                        "fetched_at": now,
                    },
                )
                .returning(KnowledgeDocumentOrm.id)
            )
            result = session.execute(statement).scalar_one()
            return result

    def replace_chunks(
        self, knowledge_document_id: UUID, chunks: Iterable[KnowledgeChunk]
    ) -> None:
        chunks_list = list(chunks)
        with session_scope() as session:
            # Delete then re-insert in one transaction.
            session.query(KnowledgeChunkOrm).filter(
                KnowledgeChunkOrm.knowledge_document_id == knowledge_document_id
            ).delete(synchronize_session=False)

            for chunk in chunks_list:
                session.add(
                    KnowledgeChunkOrm(
                        id=chunk.id,
                        knowledge_document_id=knowledge_document_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        embedding=list(chunk.embedding) if chunk.embedding else None,
                        metadata_jsonb=chunk.metadata or None,
                    )
                )

    def get_document(self, document_id: UUID) -> KnowledgeDocument | None:
        with session_scope() as session:
            row = session.get(KnowledgeDocumentOrm, document_id)
            return _to_domain(row) if row else None

    def get_document_by_source(
        self, source: KnowledgeSourceKind, source_id: str
    ) -> KnowledgeDocument | None:
        with session_scope() as session:
            statement = select(KnowledgeDocumentOrm).where(
                KnowledgeDocumentOrm.source == source.value,
                KnowledgeDocumentOrm.source_id == source_id,
            )
            row = session.execute(statement).scalar_one_or_none()
            return _to_domain(row) if row else None

    def list_documents(
        self, source: KnowledgeSourceKind | None = None
    ) -> Iterable[KnowledgeDocument]:
        with session_scope() as session:
            statement = select(KnowledgeDocumentOrm)
            if source is not None:
                statement = statement.where(KnowledgeDocumentOrm.source == source.value)
            return [_to_domain(row) for row in session.execute(statement).scalars()]

    def count_chunks(self) -> int:
        with session_scope() as session:
            return session.query(KnowledgeChunkOrm).count()


def _to_domain(row: KnowledgeDocumentOrm) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=row.id,
        source=KnowledgeSourceKind(row.source),
        source_id=row.source_id,
        title=row.title,
        raw_body=row.raw_body,
        source_url=row.source_url,
        last_updated_at=row.last_updated_at,
        fetched_at=row.fetched_at,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
