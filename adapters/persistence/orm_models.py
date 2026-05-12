"""SQLAlchemy declarative models for the persistence layer.

These are the only place SQLAlchemy `Column` / `Mapped` annotations appear in
the codebase. Domain entities (`domain/feedback.py` etc.) are plain Python
dataclasses; the repository converts between them and these ORM rows.

Schema decisions (matches plan section 5 + 8a):
- `feedback.UNIQUE(channel, app_slug, external_id)` enforces dedupe atomically.
- Composite index `(app_slug, platform, received_at DESC)` powers the dashboard's
  most common query: "show me recent feedback for ET on iOS."
- Composite index `(channel, app_slug, received_at)` powers spike-window joins.
- `ingestion_cursor` is keyed by `(channel, app_slug)` so each source instance
  resumes from its own last position.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSION = 768


class Base(DeclarativeBase):
    pass


class FeedbackOrm(Base):
    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    app_slug: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)

    author_identifier: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_text: Mapped[str] = mapped_column(nullable=False)
    normalised_text: Mapped[str | None] = mapped_column(nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_review_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    received_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    metadata_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("channel", "app_slug", "external_id", name="uq_feedback_dedupe"),
        # Dashboard's main filter shape: recent feedback for one (app, platform).
        Index(
            "ix_feedback_app_platform_received_at",
            "app_slug",
            "platform",
            "received_at",
        ),
        # Spike-window queries: scoped per (channel, app) over a time window.
        Index(
            "ix_feedback_channel_app_received_at",
            "channel",
            "app_slug",
            "received_at",
        ),
    )


class IngestionCursorOrm(Base):
    __tablename__ = "ingestion_cursor"

    channel: Mapped[str] = mapped_column(String(32), primary_key=True)
    app_slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    cursor_value: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class ClassificationOrm(Base):
    """Structured judgment a language model produced for one Feedback.

    Primary key is the feedback id, so a feedback has at most one classification.
    Re-classification overwrites the row; we keep `language_model_used` and
    `classified_at` so an analyst can tell which model produced what.
    """

    __tablename__ = "classification"

    feedback_id: Mapped[UUID] = mapped_column(
        ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True
    )

    category: Mapped[str] = mapped_column(String(32), nullable=False)
    sub_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    requires_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    entities_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    language_model_used: Mapped[str] = mapped_column(String(32), nullable=False)
    classified_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        # Filter feedback by category/severity efficiently for the dashboard.
        Index("ix_classification_category", "category"),
        Index("ix_classification_severity", "severity"),
    )


class FeedbackClusterOrm(Base):
    """Group of semantically similar feedback items.

    `embedding_centroid` is the running mean of member embeddings — kept
    fresh by the repository every time a new member is added. The HNSW
    index on the centroid powers the "find the closest existing cluster"
    lookup for incoming feedback.
    """

    __tablename__ = "feedback_cluster"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_centroid: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=False
    )
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_feedback_cluster_centroid_hnsw",
            "embedding_centroid",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding_centroid": "vector_cosine_ops"},
        ),
    )


class FeedbackClusterMembershipOrm(Base):
    """Many-to-one relationship: each feedback belongs to at most one cluster."""

    __tablename__ = "feedback_cluster_membership"

    feedback_id: Mapped[UUID] = mapped_column(
        ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True
    )
    cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("feedback_cluster.id", ondelete="CASCADE"), nullable=False
    )
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    # Denormalised onto the membership row so the spike-volume query can
    # window by time without joining the feedback table.
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    __table_args__ = (
        # Drives "list all members of cluster X" for the dashboard drill-down.
        Index("ix_feedback_cluster_membership_cluster", "cluster_id"),
        # Drives the spike-volume rolling-window query.
        Index(
            "ix_feedback_cluster_membership_cluster_received_at",
            "cluster_id",
            "received_at",
        ),
    )


class DraftReplyOrm(Base):
    """A drafted reply for one feedback. Phase 1d.

    Lifecycle: draft → (sent | edited | rejected | regenerated). Support
    staff review the draft, optionally edit (`edited_body`), then mark
    sent. Re-running the drafter creates a fresh `draft` row only if no
    `sent` row already exists for the same feedback — we never regenerate
    a draft after a human accepted it.

    `citations_jsonb` carries the per-citation breadcrumb (chunk_id,
    source_url, source_title, snippet) the dashboard surfaces beside the
    draft so support staff can verify every claim by clicking through.
    """

    __tablename__ = "draft_reply"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    feedback_id: Mapped[UUID] = mapped_column(
        ForeignKey("feedback.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(8), nullable=False)
    body: Mapped[str] = mapped_column(nullable=False)
    citations_jsonb: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    edited_body: Mapped[str | None] = mapped_column(nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    metadata_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        # Drives the inbox query: "drafts pending for this app/channel".
        Index("ix_draft_reply_feedback", "feedback_id"),
        Index("ix_draft_reply_status_generated_at", "status", "generated_at"),
    )


class SpikeEventOrm(Base):
    """A recorded spike: one row per (cluster × detection-window) firing.

    Re-detection within the suppression window is suppressed by the use case
    so the digest doesn't re-alert the same trend repeatedly. We keep the
    sample feedback_ids the spike fired with so the digest can show
    "here's what people are saying."
    """

    __tablename__ = "spike_event"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("feedback_cluster.id", ondelete="CASCADE"), nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline: Mapped[float] = mapped_column(Float, nullable=False)
    ratio: Mapped[float] = mapped_column(Float, nullable=False)
    sample_feedback_ids_jsonb: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    alerted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        # Drives "spikes since X" and "recent spike for cluster X" lookups.
        Index("ix_spike_event_cluster_window_end", "cluster_id", "window_end"),
        Index("ix_spike_event_window_end", "window_end"),
    )


class KnowledgeDocumentOrm(Base):
    """One page/issue/sheet from an external knowledge source.

    Unique key is (source, source_id) — re-syncing the same source from
    Confluence/JIRA/Sheets updates this row in place rather than creating
    a duplicate. Re-sync also calls `replace_chunks` to atomically swap
    the chunk set so stale chunks from a previous version don't linger.
    """

    __tablename__ = "knowledge_document"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_body: Mapped[str] = mapped_column(nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_knowledge_document_source"),
        Index("ix_knowledge_document_source", "source"),
    )


class KnowledgeChunkOrm(Base):
    """A retrieval-sized slice of one knowledge document.

    Each chunk carries:

    - `embedding` (vector(768)) — for semantic similarity. HNSW-indexed.
    - `content_tsvector` — a generated full-text-search column maintained
      automatically by Postgres. The 'simple' configuration tokenises on
      whitespace + punctuation without language-specific stemming, which
      works for English exact-token matches (TOI-4521, v8.4) and gives
      reasonable behaviour on Hindi / Tamil / Marathi tokens too.

    The retriever queries both and merges via reciprocal rank fusion.
    """

    __tablename__ = "knowledge_chunk"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    knowledge_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    # Generated column — Postgres derives this from `content` on every
    # insert/update. The repository never sets it directly.
    content_tsvector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', content)", persisted=True),
    )
    metadata_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "knowledge_document_id", "chunk_index", name="uq_knowledge_chunk_position"
        ),
        # Drives "list chunks for one document" — used by replace_chunks and citations.
        Index("ix_knowledge_chunk_document", "knowledge_document_id"),
        # Vector similarity index for semantic search.
        Index(
            "ix_knowledge_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Full-text search index for lexical matches.
        Index(
            "ix_knowledge_chunk_tsvector_gin",
            "content_tsvector",
            postgresql_using="gin",
        ),
    )


class DigestLogOrm(Base):
    """One row per stakeholder digest sent (or attempted).

    Lets ops verify hourly/daily digests fired and inspect the body that
    went out. `error` captures partial-failure modes so the next run can
    self-diagnose.
    """

    __tablename__ = "digest_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # "hourly" | "daily"
    body_html: Mapped[str] = mapped_column(nullable=False)
    recipients_jsonb: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    error: Mapped[str | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_digest_log_type_sent_at", "type", "sent_at"),
    )


class AuditLogOrm(Base):
    """One row per recorded system action.

    Append-only audit trail. Cron entry-points write `started` /
    `finished` rows; significant events (drafts delivered, spikes
    detected, digests sent) write entity-scoped rows. The Postgres
    adapter never updates or deletes rows here.

    `details` is intentionally `JSONB` and free-form — different call
    sites care about different metadata (counts, fix versions,
    recipient lists) and we don't want each to drive a schema change.
    The dashboard renders it as key/value pairs.
    """

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    details_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    __table_args__ = (
        # Newest-first queries are the common read pattern.
        Index("ix_audit_log_occurred_at_desc", "occurred_at"),
        # "What did the X cron do?" is the common filter.
        Index("ix_audit_log_actor_occurred_at", "actor", "occurred_at"),
    )
