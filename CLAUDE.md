# CLAUDE.md

Read this file before making any change to this codebase. It's short on
purpose — every line is a constraint that earlier work has paid for.

## What this project is

The Times of India Support Automation system: cron-driven pipeline that
ingests user feedback (Gmail, Google Play, Apple App Store) for multiple
Times Internet apps, classifies and clusters complaints with an LLM and
embeddings, detects spikes, drafts replies grounded in internal
knowledge (Confluence / JIRA / Sheets), and emails stakeholder digests.

For the full design narrative see `docs/ARCHITECTURE.md` and
`docs/DECISIONS.md`. The original brainstorm + plan lives at
`~/.claude/plans/we-have-to-brainstorm-gleaming-globe.md`.

## The dependency rule (read once, never violate)

```
   entrypoints/   (CLI cron + web API + UI)
        ↓
   adapters/      (Postgres, LLM CLIs, Gmail, JIRA, …)
        ↓
   service_layer/ (use cases + ports)
        ↓
   domain/        (entities, pure types, no I/O)
```

**Imports flow inward only.** A use case never imports an adapter. A
domain type never imports anything app-specific. Adapters implement the
Protocols defined in `service_layer/ports/`.

Concrete invariants you can grep for:

- Only `adapters/persistence/` imports `sqlalchemy`. Everything else
  speaks to the database via `FeedbackRepositoryPort`,
  `ClassificationRepositoryPort`, etc.
- Only `adapters/retrieval/` knows about pgvector cosine, chunking, and
  hybrid retrieval. The drafter (when it lands) depends on
  `KnowledgeRetrieverPort`, not on `vector_index.py`.
- Only `adapters/language_models/` runs subprocesses or makes outbound
  HTTP for LLM inference. Use cases see `LanguageModelPort`.
- `web_ui/` is a separate npm/Vite project; nothing in Python imports
  from it. Removing `web_ui/` plus the one mount line in
  `entrypoints/web_api/static_mount.py` leaves a working API + CLI.

## Where things live

| Folder | What |
|---|---|
| `domain/` | Entities + value objects. Pure Python. |
| `service_layer/ports/` | Protocols (interfaces) the use cases depend on. |
| `service_layer/use_cases/` | One file per use case (IngestFeedback, ClassifyFeedback, …). |
| `adapters/feedback_sources/` | Inbound channels: Gmail / Play / Apple. Real + local variants. |
| `adapters/knowledge_sources/` | Confluence / JIRA / Sheets. Real + local variants. |
| `adapters/persistence/` | The SQL layer. The only directory allowed to `import sqlalchemy`. |
| `adapters/retrieval/` | Document chunker, vector + lexical search, hybrid retriever (reciprocal rank fusion). Citation builder lands with the drafter (phase 1d). |
| `adapters/language_models/` | Claude Code, Codex, Ollama Gemma, RecordedResponse — all behind the same `LanguageModelPort`. |
| `adapters/embedding_models/` | Local sentence-transformer (`multilingual-e5-base`). Lazy-loaded — only paid by clustering / retrieval, not by ingest. |
| `adapters/notification/` | SMTP sender + local file writer for digests. |
| `entrypoints/cli/` | One Python module per cron job. Each runs inside a `cron_lock` advisory lock when on Postgres. |
| `entrypoints/web_api/` | (Future) FastAPI JSON-only routes. |
| `entrypoints/composition_root.py` | The single place that wires ports → adapters. Use cases and the web API never instantiate adapters directly. |
| `data_fixtures/` | Dummy data for local mode. Every external source has a `local_*` adapter that reads from here so the system runs end-to-end with **zero real credentials**. |
| `secrets/` | Real credentials. `.gitignore`d. See `secrets/README.md`. |
| `prompts/` | LLM prompt templates as Markdown. Brace-escape (`{{` `}}`) any literal `{` `}` inside the description text — the prompt builder uses `str.format()`. |
| `config_files/` | Operator-tunable YAML: apps, thresholds, stakeholders, language model chain. Engineer-managed (no UI for editing). |
| `tests/unit/` | No I/O. Use fakes for every port. Run on every commit. |
| `tests/integration/persistence/` | Real Postgres. Skips cleanly without `SUPPORT_AUTOMATION_DATABASE_URL`. Uses a separate `_test`-suffixed database. |
| `tests/integration/feedback_sources/` | Reads the shipped fixtures. |
| `tests/integration/knowledge_sources/` | Reads the shipped knowledge fixtures. |

## Naming and style rules

- **No abbreviations in identifiers.** It's `knowledge_base`, not `kb`.
  `language_model`, not `llm`. `feedback_repository_postgres`, not
  `repo`. Class names match: `KnowledgeRepositoryPostgres`, not
  `KBRepoPg`. The full names cost a few extra keystrokes and save every
  reader's translation step.
- **Docstrings explain WHY, not what.** The code shows what; the
  comment explains the constraint, the invariant, or the trade-off
  that's not obvious from reading.
- **Two adapter implementations per external port** — one real, one
  local that reads fixtures from `data_fixtures/`. Real adapters arrive
  as separate files; the in-memory persistence siblings stay
  permanently for tests.
- **Never modify the plan file** (`~/.claude/plans/...`) outside an
  explicit planning session. Add new design notes to
  `docs/DECISIONS.md` instead.

## How to run things

```bash
# One-time setup
make setup-postgres                       # PostgreSQL 16 + pgvector via Homebrew
.venv/bin/pip install -e ".[dev]"         # Python deps
.venv/bin/python scripts/bootstrap_schema.py  # Create the tables

# Daily commands
.venv/bin/python -m pytest                                                 # ~170 tests, < 1.5 seconds
.venv/bin/python -m entrypoints.cli.ingest_feedback_cli --once             # Pull new feedback
.venv/bin/python -m entrypoints.cli.classify_and_cluster_cli --once        # Classify + cluster
.venv/bin/python -m entrypoints.cli.sync_knowledge_base_cli --once         # Sync Confluence / JIRA / Sheets
.venv/bin/python -m entrypoints.cli.detect_spikes_cli --once               # Find clusters that spiked
.venv/bin/python -m entrypoints.cli.send_digest_cli --type=daily --once    # Build + send (or write) the digest
.venv/bin/python -m entrypoints.cli.query_knowledge_cli "video crash"      # Smoke-test retrieval against a free-text query
.venv/bin/python -m entrypoints.cli.draft_replies_cli --once               # Draft a reply for every follow-up-worthy feedback
.venv/bin/uvicorn entrypoints.web_api.main:app --port 8080                 # Start the read-only JSON API (127.0.0.1:8080)

# Postgres mode (everything above stays the same; just export this)
export SUPPORT_AUTOMATION_DATABASE_URL=postgresql+psycopg://$USER@localhost/support_automation_local
```

## Working in this codebase as Claude

When asked to add a new feature:

1. Identify which **layer** the change belongs to. New use case → `service_layer/use_cases/`. New external integration → `adapters/<kind>/`. New cron entry-point → `entrypoints/cli/`.
2. **Define the port first** if a use case needs something new from the outside world. The Protocol goes in `service_layer/ports/`.
3. **Write the in-memory adapter and the use-case test together**, with the test driving the design. Then add the Postgres / real adapter.
4. **Wire it into `entrypoints/composition_root.py`** — every other entry-point reads from the wired graph there.
5. **Update `docs/ARCHITECTURE.md` and `docs/DECISIONS.md`** if the change is structural.

When asked to debug:

1. Run `.venv/bin/python -m pytest -v` first. If anything is red, fix that before chasing the reported issue.
2. Read the relevant use case + its port, then look at the adapter. The bug is almost always in an adapter — the use cases are pure orchestration.
3. For Postgres-only failures, check the test database (`support_automation_local_test`) and the main database (`support_automation_local`) separately. The conftest auto-creates the test database; the main database is bootstrapped via `scripts/bootstrap_schema.py`.

## What's deliberately not built (and why)

- **Real-mode source adapters for Gmail / Play / Apple / Confluence /
  JIRA / Sheets** — each `*_knowledge_source.py` and
  `*_feedback_source.py` is on the backlog. Local adapters cover all
  development and CI today; real adapters arrive when going live with a
  given source. Per-source steps live in `docs/HANDBOOK.md`.
- **Auth for the dashboard** — system runs on a single internal VM bound
  to `127.0.0.1`. Per ADR-006 in `docs/DECISIONS.md`, we trust the VM
  perimeter and skip auth in phase 1.
- **Agentic memory** — covered by Postgres + RAG. See ADR-014.
- **Cross-encoder reranking, smart team routing, exemplar store, spike-
  investigation agent** — all phase-2 backlog. See `docs/DECISIONS.md`
  for context on why each is deferred.

## What to do if something here is wrong

These constraints are paid for in past pain. Before relaxing any of them,
read the matching ADR in `docs/DECISIONS.md`. If you still think it
should change, write a new ADR explaining why and link the previous one
as superseded.
