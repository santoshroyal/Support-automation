# Architecture

A walk-through of how the Times of India Support Automation system is built
and how data flows through it. For the *why* behind specific choices, see
[`DECISIONS.md`](DECISIONS.md). For day-to-day operator instructions, see
[`HANDBOOK.md`](HANDBOOK.md). For conventions when modifying the codebase,
see [`../CLAUDE.md`](../CLAUDE.md).

## The 30-second pitch

User feedback comes in from three channels (Gmail, Google Play, Apple App
Store) for several Times Internet apps (Times of India, Economic Times,
Navbharat Times). The system pulls it on a schedule, classifies and groups
similar complaints, watches for sudden spikes, drafts replies grounded in
internal knowledge sources (Confluence pages, JIRA tickets, Google Sheets
trackers), and emails stakeholders a digest when something fires. Support
staff review and send the drafts; they don't run anything themselves —
they're consumers of a read-only dashboard.

## Layered architecture (the dependency rule)

The codebase follows the ports-and-adapters / clean-architecture pattern.
Imports flow inward only:

```
   ┌─────────────────────────────────────────────────────────────────┐
   │  entrypoints/                                                   │
   │  cron CLIs · web API · React SPA                                │
   │   ┌───────────────────────────────────────────────────────────┐ │
   │   │  adapters/                                                │ │
   │   │  Postgres · pgvector · Gmail · JIRA · LLM CLIs · SMTP     │ │
   │   │   ┌─────────────────────────────────────────────────────┐ │ │
   │   │   │  service_layer/                                     │ │ │
   │   │   │  use cases (IngestFeedback, ClassifyFeedback, …)    │ │ │
   │   │   │  + ports (Protocols)                                │ │ │
   │   │   │   ┌───────────────────────────────────────────────┐ │ │ │
   │   │   │   │  domain/                                      │ │ │ │
   │   │   │   │  Feedback, Classification, FeedbackCluster,   │ │ │ │
   │   │   │   │  KnowledgeDocument, DraftReply, SpikeEvent    │ │ │ │
   │   │   │   │  (pure Python, no I/O)                        │ │ │ │
   │   │   │   └───────────────────────────────────────────────┘ │ │ │
   │   │   └─────────────────────────────────────────────────────┘ │ │
   │   └───────────────────────────────────────────────────────────┘ │
   └─────────────────────────────────────────────────────────────────┘
```

What that buys us:

- **`domain/` survives any rewrite of every other layer.** It's just
  Python dataclasses + enums.
- **Use cases are testable without touching anything external.** Every
  test in `tests/unit/service_layer/` runs in milliseconds against fake
  in-memory adapters.
- **Swapping Postgres for SQLite, or Claude for Codex, touches only one
  folder.** Use cases and the API surface don't change.

## Component data flow

```
                ┌──────────────────────────────────────────────────────┐
                │                External sources                      │
                │  Gmail · Play Console · App Store Connect            │
                │   │           │                │                     │
                │   ▼           ▼                ▼                     │
                │  Confluence · JIRA · Google Sheets                   │
                └───┬───────────┬────────────────┬─────────────────────┘
                    │           │                │
        ┌───────────▼───┐  ┌────▼────────────────▼────┐
        │ IngestFeedback│  │ SyncKnowledgeBase        │  every 90 min
        │ every 15 min  │  └─────────────┬────────────┘
        └───────┬───────┘                │
                │                        ▼
                │          ┌─────────────────────────────┐
                │          │ knowledge_chunk             │
                │          │ + embedding (pgvector HNSW) │
                │          │ + tsvector (lexical)        │
                │          └─────────────────────────────┘
                ▼
        ┌──────────────────────┐         ┌──────────────────────────┐
        │ ClassifyFeedback     │────────▶│ ClusterFeedback          │
        │ language model →     │         │ embedding → cluster      │
        │ category, severity   │         │ (pgvector cosine search) │
        └─────────┬────────────┘         └────────────┬─────────────┘
                  │                                   │
                  ▼                                   ▼
        ┌────────────────────────┐         ┌──────────────────────────┐
        │ DetectComplaintSpike   │         │ DraftFeedbackReply       │
        │ rolling 24h vs 7d      │         │ (phase 1d) RAG + LLM     │
        │ baseline               │         └────────────┬─────────────┘
        └────────────┬───────────┘                      │
                     │                                  ▼
                     ▼                       ┌────────────────────────┐
        ┌────────────────────────┐           │ Gmail draft writer     │
        │ SendStakeholderDigest  │           │ + filesystem writer    │
        │ HTML body, SMTP / file │           └────────────────────────┘
        └────────────────────────┘

        ┌────────────────────────────────────────────────────────────┐
        │ Read-only consumer dashboard (phases 1f + 1g)              │
        │ React SPA over FastAPI JSON; users filter and view, never  │
        │ mutate. Settings + thresholds + prompts stay engineer-     │
        │ managed in YAML / Markdown files.                          │
        └────────────────────────────────────────────────────────────┘
```

## What's wired today vs what's pending

| Phase | Status | Visible in the database |
|---|---|---|
| 1a — Ingestion (3 channels × 3 apps × multilingual) | ✅ shipped | `feedback`, `ingestion_cursor` |
| 1b — Classification + clustering | ✅ shipped | `classification`, `feedback_cluster`, `feedback_cluster_membership` |
| 1c-1 — Knowledge base sync | ✅ shipped | `knowledge_document`, `knowledge_chunk` |
| 1c-2 — Hybrid retrieval (vector + lexical + RRF) | ✅ shipped | adds `content_tsvector` generated column + GIN index on `knowledge_chunk` |
| 1d — Drafting + delivery | ✅ shipped | `draft_reply` |
| 1e — Spike detection + digest | ✅ shipped | `spike_event`, `digest_log` |
| 1f — JSON API (FastAPI) | ✅ shipped (health, apps, feedback, drafts, spikes, knowledge/sources, analytics/volume, analytics/categories) | (no new tables) |
| 1g — React UI | ✅ shipped (Vite + React + TS + Tailwind + shadcn + TanStack Query + Recharts; 5 pages; isolation enforced by `make ci-headless`) | (no new tables) |
| 1h — Hardening | ⏳ pending | `audit_log` |

Test count today: **157** (90 unit + 17 file-based integration + 15 Postgres integration + 35 API). Every PR
runs the unit suite; integration tests run when
`SUPPORT_AUTOMATION_DATABASE_URL` is set.

## Database schema (current state)

Eleven tables. All UUIDs are primary keys; all timestamps are timezone-aware.

| Table | Purpose | Key constraints |
|---|---|---|
| `feedback` | Every ingested feedback item across all channels | `UNIQUE(channel, app_slug, external_id)` for atomic dedupe; `(app_slug, platform, received_at)` index for dashboard filters |
| `ingestion_cursor` | Per-source resume marker | PK `(channel, app_slug)`; updated via `GREATEST(...)` to avoid regression |
| `classification` | Structured judgment per feedback | PK = `feedback_id` (one classification per feedback); upserts on re-classification |
| `feedback_cluster` | Group of semantically similar feedback | `embedding_centroid vector(768)` with HNSW + `vector_cosine_ops` |
| `feedback_cluster_membership` | Many-to-one feedback↔cluster | `received_at` denormalised so spike-volume query needs no join |
| `knowledge_document` | One Confluence page / JIRA ticket / Sheet | `UNIQUE(source, source_id)` for upsert |
| `knowledge_chunk` | ~500-character slice with embedding | `vector(768)` + HNSW; `content_tsvector` (generated column) + GIN for lexical search |
| `spike_event` | Recorded spike; cluster × window | Suppression via `ix_spike_event_cluster_window_end` |
| `digest_log` | Audit of every digest run | `(type, sent_at)` index; `error` column captures partial failures |
| (planned) `draft_reply` | Generated drafts with citations | Phase 1d |
| (planned) `audit_log` | Cron-side action history | Phase 1h |

Full DDL lives in `adapters/persistence/orm_models.py`. Re-run
`scripts/bootstrap_schema.py` to materialise it.

## External dependencies

| Dependency | Used by | Notes |
|---|---|---|
| **PostgreSQL 16** | Everything | Native install via Homebrew, single instance. |
| **pgvector 0.8.0** | Cluster centroid search, knowledge chunk search | Built from source against PostgreSQL 16 (the Homebrew bottle is for 17/18). |
| **multilingual-e5-base (sentence-transformers)** | Cluster + knowledge embeddings | Local CPU model, ~250 MB, downloaded once and cached. Lazy-loaded. |
| **Claude Code CLI** | Classification + drafting | Subprocess `claude -p ...`. Uses the user's terminal subscription, no API key. |
| **Codex CLI / Ollama Gemma** | Fallback LLMs | Same router pattern. Ollama only counts as healthy when the model is pulled. |
| **`sqlalchemy 2`, `psycopg 3`, `alembic`** | Persistence | Confined to `adapters/persistence/`. |
| **`fastapi` + `uvicorn`** | (Future) JSON API | Phase 1f. |
| **React + Vite + Tailwind + shadcn/ui** | (Future) Dashboard | Phase 1g. Lives in `web_ui/`, separate npm project. |

## Concurrency model (single-host, cron-driven)

The system runs on **one** Linux VM with **one** PostgreSQL instance.
Cron jobs are the only writers; dashboard users are read-only consumers.

| Hazard | Mitigation |
|---|---|
| Two cron runs of the same job overlap | `pg_try_advisory_lock(hashtext('<job-name>'))` at the top of every entry-point. Late-comers exit cleanly. |
| Duplicate inserts inside one cron run (retry, partial replay) | `INSERT … ON CONFLICT (channel, app_slug, external_id) DO NOTHING` for feedback; same pattern for classification (DO UPDATE), knowledge documents (DO UPDATE), cluster centroids (idempotent UUIDs). |
| Cursor regression if the same job parallelises | `UPDATE ingestion_cursor SET cursor_value = GREATEST(cursor_value, :new)`. |
| Long-running cron job hits the idle-in-transaction timeout | Cron lock connection runs in `AUTOCOMMIT` isolation so it's never *in* a transaction while the work runs (sometimes 75+ seconds for 15 LLM calls). |
| Dashboard reads collide with cron writes | PostgreSQL MVCC — readers never block writers and vice versa. |
| Connection pool exhaustion | Pool sized 25 (15 reader headroom + 7 cron + 3 spare). `statement_timeout` and `idle_in_transaction_session_timeout` cap pathological queries. |

A 50-thread concurrent-ingest stress test
(`tests/integration/persistence/test_concurrent_ingest_stress.py`)
guards these properties on every change.

## Local mode vs real mode

Every external source has **two adapter implementations**:

- **Real adapter** (`gmail_feedback_source.py`, `confluence_knowledge_source.py`, …)
  calls the live API using credentials in `secrets/`.
- **Local adapter** (`local_*.py`) reads fixture files from
  `data_fixtures/`.

The composition root chooses per source based on a `mode` setting (today
all `local`; flipping to `real` is documented per source in
[`HANDBOOK.md`](HANDBOOK.md)). Notification works the same way:
`local_email_sender` writes the digest to `var/log/digests/`,
`smtp_email_sender` actually delivers email.

The default development experience is **fully local — zero credentials**.
CI runs in this mode. Real adapters arrive incrementally as each source
goes live.

## Where to read more

- [`CLAUDE.md`](../CLAUDE.md) — conventions for editing the codebase.
- [`DECISIONS.md`](DECISIONS.md) — every significant choice and why.
- [`HANDBOOK.md`](HANDBOOK.md) — how an operator brings real sources online.
- `adapters/persistence/orm_models.py` — current schema in code.
- `entrypoints/composition_root.py` — the wiring graph.
