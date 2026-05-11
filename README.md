# Times of India — Support Automation

A cron-driven pipeline that ingests user feedback (Gmail, Google Play,
Apple App Store) for several Times Internet apps, classifies and groups
similar complaints, watches for sudden spikes, drafts replies grounded
in internal knowledge sources (Confluence, JIRA, Sheets), and emails
stakeholder digests.

Support staff review and send the drafts; they don't run anything
themselves — they're consumers of a read-only dashboard.

## Where to start reading

| If you're … | Read this first |
|---|---|
| **A new contributor** opening the repo for the first time | [`CLAUDE.md`](CLAUDE.md) — the conventions and invariants in 3 minutes |
| **Reviewing or extending the architecture** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layer model, schema, data flow, what's wired today |
| **Asking "why did we choose X?"** | [`docs/DECISIONS.md`](docs/DECISIONS.md) — every significant choice as a numbered ADR |
| **An operator going live with real sources** | [`docs/HANDBOOK.md`](docs/HANDBOOK.md) — per-source credential setup, going-live checklist, rollback |
| **Debugging or wiring a new use case** | `entrypoints/composition_root.py` — the wiring graph |
| **Looking at the schema** | `adapters/persistence/orm_models.py` — current tables, indexes, FKs |

## What works today

Everything below runs end-to-end with **zero real credentials** —
fixtures in `data_fixtures/` cover every external source.

```bash
# One-time setup
make setup-postgres                                      # PostgreSQL 16 + pgvector
.venv/bin/pip install -e ".[dev]"
.venv/bin/python scripts/bootstrap_schema.py
export SUPPORT_AUTOMATION_DATABASE_URL=postgresql+psycopg://$USER@localhost/support_automation_local

# Run the full pipeline once
.venv/bin/python -m entrypoints.cli.ingest_feedback_cli --once
.venv/bin/python -m entrypoints.cli.classify_and_cluster_cli --once
.venv/bin/python -m entrypoints.cli.sync_knowledge_base_cli --once
.venv/bin/python -m entrypoints.cli.detect_spikes_cli --once
.venv/bin/python -m entrypoints.cli.send_digest_cli --type=daily --once

# See the digest that just got written
ls var/log/digests/

# Smoke-test retrieval against any free-text query
.venv/bin/python -m entrypoints.cli.query_knowledge_cli "video player crash on iPhone"

# Draft replies for every classified, follow-up-worthy feedback
.venv/bin/python -m entrypoints.cli.draft_replies_cli --once
ls var/support_automation/drafts/   # one Markdown draft per feedback

# Start the JSON API (binds to 127.0.0.1:8080)
.venv/bin/uvicorn entrypoints.web_api.main:app --host 127.0.0.1 --port 8080
# In another terminal:
curl http://127.0.0.1:8080/api/health
curl http://127.0.0.1:8080/api/apps
curl "http://127.0.0.1:8080/api/feedback?app=toi&platform=ios"
```

After this you'll have:

- 15 feedback rows across 3 apps × 3 channels in `feedback`
- 15 real Claude classifications in `classification`
- 8 clusters in `feedback_cluster` (40 cluster memberships)
- 17 knowledge documents → 40 chunks in `knowledge_document` /
  `knowledge_chunk`, each carrying a 768-dim embedding
- 1 spike event in `spike_event`
- 1 daily digest HTML file in `var/log/digests/`

Inspect any of the above in Postico, TablePlus, DBeaver, or any other
PostgreSQL client.

## Running the tests

```bash
.venv/bin/python -m pytest -v
```

Expect **157 tests passing** (90 unit + 17 file-based integration + 15 PostgreSQL integration + 35 API tests).
The unit suite runs in milliseconds against fakes; the integration
suite needs `SUPPORT_AUTOMATION_DATABASE_URL` set and uses a separate
`*_test`-suffixed database, so it never touches your main data.

## Folder map (one-liner per top-level directory)

| Folder | Purpose |
|---|---|
| `domain/` | Pure-Python entities and value objects. No I/O. |
| `service_layer/` | Use cases + the Protocols (ports) they depend on. |
| `adapters/` | Concrete implementations of every port. |
| `entrypoints/` | CLI cron jobs + (future) FastAPI service. |
| `web_ui/` | (future) React SPA, fully isolated. |
| `data_fixtures/` | Dummy data for local mode — no credentials needed. |
| `secrets/` | Real credentials. Gitignored. |
| `prompts/` | LLM prompt templates as Markdown. |
| `config_files/` | Operator-tunable YAML (apps, thresholds, stakeholders, model chain). |
| `scripts/` | Operator + dev helpers (`bootstrap_schema.py`, `record_llm_responses.py`, etc.). |
| `tests/unit/` + `tests/integration/` | Test suites. |
| `docs/` | Architecture, decisions, handbook (the docs you're navigating from). |

## Phase-1 status at a glance

| Phase | Description | Status |
|---|---|---|
| 1a | Multi-app, multi-platform feedback ingestion | ✅ shipped |
| 1b | Classification + clustering (real Claude + multilingual embeddings) | ✅ shipped |
| 1c-1 | Knowledge base sync (Confluence, JIRA, Sheets → chunks + embeddings) | ✅ shipped |
| 1c-2 | Hybrid retrieval (vector + lexical + RRF) | ✅ shipped |
| 1d | Drafting + delivery (RAG-grounded replies, filesystem writer; Gmail real adapter pending credentials) | ✅ shipped |
| 1e | Spike detection + stakeholder digest | ✅ shipped |
| 1f | Read-only JSON API (FastAPI) — health, apps, feedback, drafts, spikes, knowledge/sources, analytics/volume, analytics/categories | ✅ shipped |
| 1g | React dashboard | ⏳ pending |
| 1h | Hardening (audit log, runbook, systemd timers) | ⏳ pending |

The original brainstorm + plan lives at
`~/.claude/plans/we-have-to-brainstorm-gleaming-globe.md`.
