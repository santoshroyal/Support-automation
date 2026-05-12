# Architecture Decision Records

Each entry captures **one** significant choice. Format:

- **Context** — what problem prompted the decision
- **Decision** — what we picked
- **Consequences** — what we get and what we give up

Numbered chronologically. New entries go at the bottom; superseded ones
get a "Superseded by ADR-NNN" line and stay for the historical record.

---

## ADR-001 — Clean Architecture / ports-and-adapters

**Context.** The system has 7+ external integrations (Gmail, Play, App
Store, Confluence, JIRA, Sheets, SMTP, three LLM CLIs). Without
discipline, those integrations would leak into use cases, making each
swap (e.g. local mode → real mode) a sweeping rewrite.

**Decision.** Strict 4-layer architecture: `domain/` →
`service_layer/` (use cases + ports) → `adapters/` → `entrypoints/`.
Imports flow inward only. Use cases depend on Protocols (`*Port` files);
adapters implement them.

**Consequences.** Use cases are pure orchestration, testable in
milliseconds with fakes. Swapping any adapter touches one folder. The
trade-off: more boilerplate (one Protocol + one fake + one real adapter
per integration) than a "just call the API directly" style. Worth it at
this integration count.

---

## ADR-002 — PostgreSQL with pgvector for everything

**Context.** We need persistence for feedback/classifications/clusters/
drafts/spikes plus vector similarity search for clustering and RAG. A
naive split would be Postgres + a separate vector store (Pinecone /
Weaviate / Milvus).

**Decision.** Single PostgreSQL 16 instance with the `pgvector`
extension. All tables live there, including `vector(768)` columns on
`feedback_cluster.embedding_centroid` and `knowledge_chunk.embedding`,
both indexed with HNSW + `vector_cosine_ops`.

**Consequences.** One database to operate, one set of credentials, one
backup story, ACID across vector and relational data. The trade-off:
HNSW in pgvector is good but not as fast as a dedicated vector store at
billions-of-vectors scale. For our hundreds-to-low-thousands of chunks
this is hugely overkill in the right direction.

---

## ADR-003 — LLM access via terminal subscription, not API key

**Context.** Anthropic offers two ways to use Claude: a subscription
(via Claude Code CLI, Cowork, Desktop) or the API (HTTPS, per-token
billing). The operator already pays for a Max subscription.

**Decision.** Use the Claude Code CLI as a subprocess via the
`ClaudeCodeLanguageModel` adapter. Same pattern for `codex` (OpenAI
subscription) and `ollama` (local). The router (`LanguageModelRouter`)
picks the first healthy candidate and falls back if one fails. The
`RecordedResponseLanguageModel` is always the final fallback so the
pipeline never fails open.

**Consequences.** Zero per-token spend, no API key management. The
trade-off: a 3 am cron job needs the CLI binary and a logged-in account
on the server (we'll need to think through this when we deploy on a
machine with no human present); also, subscription rate limits apply.
Switching to the Anthropic API is a one-line composition-root change
when those limits start hurting.

---

## ADR-004 — Local-first development; no real credentials needed

**Context.** New engineers should be able to run the entire pipeline on
their laptop within minutes of cloning. CI must run on every PR without
external API quota.

**Decision.** Every external source has two adapter implementations: a
real one and a `local_*` one that reads fixture files from
`data_fixtures/`. The composition root chooses per-source via a `mode`
setting. Notification, the LLM, and the embedding model follow the same
two-implementation pattern.

**Consequences.** First-time setup is `make setup-postgres &&
.venv/bin/pip install -e .[dev] && python scripts/bootstrap_schema.py`
— no credentials, no network calls. Tests run hermetically. The
trade-off: every new external source costs us two adapter files instead
of one, plus fixture data. It's been worth it on every single sprint.

---

## ADR-005 — Multi-app, multi-platform from day 1

**Context.** TOI is the lead app, but Times Internet operates several
news apps (Economic Times, Navbharat Times, Maharashtra Times, …).
Adding multi-app support after building for TOI alone would mean a
data-model migration.

**Decision.** Every `feedback` row carries `app_slug` and `platform`.
Apps live in `config_files/apps.yaml`. Cursors are keyed by
`(channel, app_slug)` so each (app × channel) pair resumes
independently. Filters on `(app_slug, platform, channel)` are first
class everywhere — repository methods, dashboard queries, future spike
attribution.

**Consequences.** Adding a new app is one YAML entry. Filtering "show
me Economic Times iOS only" is a single repository call. The trade-off:
a few extra columns and a longer dedupe key. Negligible cost.

---

## ADR-006 — Dashboard is read-only; no auth in phase 1

**Context.** 1–15 support staff plus stakeholders use the dashboard.
Authentication, role-based access control, and write operations all
expand the attack surface and the concurrency surface.

**Decision.** Dashboard users only **read** data the cron jobs have
produced. No mark-sent button, no settings editor, no prompt editor in
the UI. Settings live in YAML edited by engineers via PR. The web
service binds to `127.0.0.1` on the internal VM; access is via SSH
tunnel.

**Consequences.** Concurrency model collapses to "one writer (cron),
many readers". No optimistic-concurrency `version` columns needed; no
`SELECT FOR UPDATE`; no auth surface to defend. The trade-off: support
staff can't ad-hoc tune the system; engineers must ship a YAML edit.
Acceptable for phase 1; worth revisiting once volume is high.

---

## ADR-007 — Cron-driven, not event-driven

**Context.** We could trigger work via webhooks (Gmail push, JIRA
webhook) or pull via cron.

**Decision.** Cron only. Cron jobs run every 15 min for ingestion +
classification + drafting; every 30 min for spike detection; every
60-90 min for digest + knowledge sync. Each entry-point grabs a
PostgreSQL advisory lock so its previous run never gets trampled.

**Consequences.** Predictable scheduling, no public-facing webhook
endpoint to defend, simpler operations. The trade-off: latency (an
incoming review can wait up to 15 minutes for ingestion) — acceptable
because support staff don't reply within 15 minutes anyway.

---

## ADR-008 — Multilingual handling: detect at ingest, embed once

**Context.** TOI users write in English, Hindi (Devanagari), Hinglish
(Roman-script Hindi), and several regional languages. A separate
embedding model per language would be a maintenance nightmare.

**Decision.** Use `intfloat/multilingual-e5-base` (sentence-transformers)
for all embeddings — single model, 768 dimensions, aligns 50+ languages
in the same vector space. Every chunk and every feedback embedding goes
through this one path.

**Consequences.** A Hindi review about a video crash and an English
JIRA ticket about the same crash end up close in vector space —
clustering and retrieval work cross-lingually for free. The trade-off:
a single model is never as good as a language-specific one for any
particular language; quality is "good", not "best". Acceptable for our
scale.

---

## ADR-009 — Recorded LLM responses for deterministic CI

**Context.** Tests that call a real LLM are slow, flaky, and burn
subscription quota.

**Decision.** Every fixture feedback has its classification prompt
recorded once via `scripts/record_llm_responses.py`, producing JSON
files in `data_fixtures/language_model_responses/` keyed by SHA-256 of
the prompt. The `RecordedResponseLanguageModel` looks up the recorded
response by prompt hash; if no match, returns a clearly-labelled
placeholder default.

**Consequences.** CI is fully deterministic — same fixtures produce the
same classifications every run. The trade-off: changing the prompt
template invalidates every recording until re-recorded. We accept the
re-record cost (~75 seconds for the current corpus) because it's rare.

---

## ADR-010 — Optimistic concurrency NOT needed

**Context.** Multi-user systems usually need version columns or
SELECT-FOR-UPDATE on shared mutable state.

**Decision.** Phase 1 has no user-driven writes (per ADR-006), and only
one writer per cron-job type at any given moment (per ADR-007 advisory
locks). So we use `INSERT … ON CONFLICT … DO NOTHING/UPDATE` for
idempotent writes and `GREATEST(...)` for monotonic cursor updates —
both of which are atomic at the SQL layer. No `version` columns
anywhere.

**Consequences.** Simpler tables. No "stale, please reload" UX. The
trade-off: the moment we add a writeable user surface (mark-sent,
settings editor), we'll need to revisit. Per ADR-006, that's not
phase 1.

---

## ADR-011 — No agentic memory in phase 1

**Context.** "Agent memory" is a hot topic. Should the LLM have
persistent memory across calls?

**Decision.** No. What an agent's memory would do is already covered:
short-term context goes in each prompt; conversational state lives on
Gmail threads (read fresh per draft); episodic memory ("what did I do
before?") lives in `draft_reply`, `spike_event`, `audit_log`; semantic
memory ("facts about the world") is the knowledge base, refreshed every
90 minutes.

**Consequences.** Every LLM call is bounded, deterministic, auditable,
and cheap. The trade-off: we can't have the system "learn" on its own
(e.g., remember the team's writing style across drafts). That's a
phase-2 idea (editorial-exemplar store, see ADR-018).

---

## ADR-012 — Hybrid retrieval: vector + lexical with reciprocal rank fusion

**Context.** Pure vector similarity misses exact-token matches like
ticket IDs (`TOI-4521`) and version numbers (`v8.4`). Pure lexical
search misses cross-language paraphrases (a Hindi paywall complaint
won't string-match an English Confluence page).

**Decision.** Run both: vector top-20 (pgvector cosine via the `<=>`
operator + HNSW index) plus lexical top-20 (PostgreSQL `tsvector` with
`plainto_tsquery` + GIN index), then merge via reciprocal rank fusion
with `k=60` (no parameter tuning needed) to top-8. That's what the
drafter sees.

**Consequences.** Catches both "video player crash" semantically (Hindi
review → English Confluence page) and `TOI-4521` literally (Gmail body
mentions the ticket → same JIRA chunk). The trade-off: two queries per
retrieval. Not a problem at our scale.

**Status.** Shipped in phase 1c-2. End-to-end verified:
`python -m entrypoints.cli.query_knowledge_cli "TOI Plus सब्सक्रिप्शन का पैसा कट गया लेकिन मेम्बरशिप नहीं मिली"`
returns the English `TOI-4530` JIRA ticket and the English Confluence
page about exactly that paywall issue.

---

## ADR-013 — Static cluster centroids in phase 1; running mean is phase-2

**Context.** When a new feedback joins a cluster, the cluster's
embedding centroid should move slightly toward the new member's
embedding (running mean). Otherwise the centroid drifts away from the
true centre as the cluster grows.

**Decision.** Phase 1 keeps the centroid at the **first** member's
embedding. Re-syncing centroids properly requires the new member's
embedding to be available at `add_membership` time. We deferred this to
keep the port surface simple in phase 1; the cluster-quality polish
backlog item adds it.

**Consequences.** Clusters work but drift over time, especially when
the first member is unrepresentative of the cluster's eventual shape.
The trade-off: clustering quality is "good enough for spike detection
to fire" but not "perfectly tight". Acceptable while we have ~20-50
clusters; matters more at thousands.

---

## ADR-014 — Cron-lock connection runs in AUTOCOMMIT isolation

**Context.** A cron job that calls 15 LLMs takes ~75 seconds. The
connection holding the advisory lock sits idle the whole time. With
`idle_in_transaction_session_timeout = 30000`, the lock connection got
killed before the work finished.

**Decision.** The lock acquisition runs on a connection derived from
`engine.execution_options(isolation_level="AUTOCOMMIT")` so the
connection is never *in* a transaction while idle. Each `SELECT
pg_try_advisory_lock(...)` and `pg_advisory_unlock(...)` commits
immediately.

**Consequences.** Cron jobs of any duration work. The trade-off: AUTOCOMMIT
means we can't wrap multiple statements in a single transaction on the
lock connection. We don't need to.

---

## ADR-015 — Test database is auto-derived from main URL with `_test` suffix

**Context.** Initial integration tests dropped tables on the **main**
database — destructive when the operator had real data in it.

**Decision.** The `tests/integration/persistence/conftest.py` derives a
test database name by appending `_test` to whatever
`SUPPORT_AUTOMATION_DATABASE_URL` points at, creates that database if
missing (also enables pgvector in it), and overrides the env var for
the test session. Schema is dropped and recreated at session start;
data is truncated between tests.

**Consequences.** Running tests after populating real data is now
safe. The trade-off: test runs need permission to `CREATE DATABASE`,
which is fine for local dev and for a managed CI database with the
right grants.

---

## ADR-016 — No abbreviations in identifiers

**Context.** Casual abbreviations (`kb`, `llm`, `repo`, `vec`) make
code skimmable for the author and incomprehensible to anyone else.

**Decision.** Full noun phrases everywhere: `knowledge_base`, not `kb`;
`language_model`, not `llm`; `feedback_repository_postgres`, not
`feedback_repo_pg`. Class names match
(`KnowledgeRepositoryPostgres`).

**Consequences.** A new contributor can read any file top-to-bottom
without translation. The trade-off: a few more keystrokes; some
deeply-nested call chains read longer. Worth it.

---

## ADR-017 — Stakeholder digest defaults to local mode (write to disk)

**Context.** Going live with real SMTP delivery on day 1 is risky —
false-positive spike alerts would land in stakeholder inboxes and erode
trust before the system has earned it.

**Decision.** Phase 1 default is `LocalEmailSender` — every digest is
written as an HTML file to `var/log/digests/<digest_type>_<timestamp>.html`.
No SMTP connection. The `SmtpEmailSender` adapter exists and is
tested; flipping to it is one line in `_build_notification_sender`
once the operator is confident in the signal.

**Consequences.** Operators get a 24-48 hour review window before real
emails land. The trade-off: until the flip, stakeholders don't see
anything. The full going-live procedure is in
[`HANDBOOK.md`](HANDBOOK.md) section G.

---

## ADR-018 — Phase-2 backlog (deferred, with reasoning)

The following are deliberately not built in phase 1. Each has a
specific signal that should trigger building it.

- **Smart team routing** (Tech vs Product vs Editorial). Deferred until
  v1 broadcast digests prove insufficient. Trigger: stakeholders
  complain about getting alerts for issues outside their area.
- **Editorial-exemplar store** (capture human edits, retrieve as
  few-shot for the next draft). Trigger: support staff routinely edit
  drafts in the same direction; we have ≥ 30 sent drafts to learn from.
- **Spike-investigation agent** (Claude Code with tools, root-cause
  hypothesis attached to the alert). Trigger: stakeholders ask "what's
  causing this?" on every digest.
- **Auto-posting to Play / App Store APIs**. Trigger: support staff
  report copy-paste fatigue with the current draft → console flow.
- **Cross-encoder reranking** on retrieval. Trigger: drafts cite the
  wrong knowledge chunks too often.
- **Multilingual UI**. Trigger: a non-English-fluent operator joins.
- **Per-user audit and authentication**. Trigger: external compliance
  requirement, or expanding the dashboard outside the VM perimeter.
- **Cowork Scheduled Tasks for operator morning briefing**. Trigger:
  the SMTP digest gets routinely ignored; operators want an
  interactive surface they can ask follow-up questions in.

---

## ADR-020 — Phase-2 retrieval-polish backlog (observed failure modes)

**Context.** Phase 1c-2 retrieval works well on the production query
pattern (a user's complaint text → relevant knowledge chunks). Two
weakness patterns surfaced when exercising the smoke-test CLI with
non-production queries:

1. **Exact-identifier queries** like `"any update on TOI-4540?"`.
   The lexical search uses `plainto_tsquery` which joins terms with
   `&` (logical AND) and ranks by `ts_rank`, which rewards chunks
   with **more** matching tokens — not the **most distinctive**
   token. A chunk with three common words ("any", "update", "on")
   beats a chunk with one rare ticket-ID ("TOI-4540"). Net result:
   the relevant chunk lands at rank 4-5 instead of rank 1.

2. **Low-coverage languages** (Tamil queries against an English-only
   knowledge base). Multilingual-e5 maps Tamil text to an Indic-
   script-adjacent vector neighbourhood, which pulls in Devanagari/
   Hindi NBT pages even when the topic doesn't match. The system
   does its best ("page is slow" → ET Markets data-lag page at
   rank 4) but the top of the result list is noisy.

**Decision.** Defer both fixes to phase-2 retrieval polish:

- **Identifier boosting** — pre-process the retriever query: regex-
  extract ticket-ID-shaped tokens (`[A-Z]+-\d+`), version strings
  (`v\d+\.\d+`), etc., and route them through a separate exact-match
  lexical query that gets a strong rank-1 weight in the RRF merge.
  Alternatively, swap `plainto_tsquery` for `websearch_to_tsquery`
  as a smaller intermediate step.
- **Language-coverage signal** — when all top-K retrieval scores are
  below a threshold, mark the retrieval as "low confidence" so the
  drafter can hedge (return a generic "we've received your feedback"
  rather than confidently cite irrelevant chunks).
- **Cross-encoder reranking** — already on the ADR-018 backlog;
  cleaner integration than identifier boosting and addresses both
  weaknesses at the cost of one extra model load.

**Consequences.** Phase 1d (drafter) ships with the current retrieval
quality. For production query patterns (complaint text → relevant
docs), this is excellent. For internal-staff queries on the future
dashboard search box, the drafter doesn't see those queries so the
gap doesn't matter yet. The trade-off is documented; we can return
to it once real production data exposes concrete cases worth
optimising for.

---

## ADR-019 — `content_tsvector` is a Postgres-generated computed column

**Context.** The lexical-search half of hybrid retrieval needs a
`tsvector` representation of every chunk's content. We had three ways
to maintain it: (1) compute it in application code on every insert,
(2) use a database trigger, (3) declare it as a `GENERATED ALWAYS AS
... STORED` column.

**Decision.** Option 3 — generated column. The DDL is one line in
`KnowledgeChunkOrm`:

```python
content_tsvector: Mapped[Any] = mapped_column(
    TSVECTOR,
    Computed("to_tsvector('simple', content)", persisted=True),
)
```

Postgres recomputes the tsvector automatically on every insert and
update of `content`. The repository never sets it; the chunker never
knows it exists.

**Consequences.** Application code stays focused on the domain
(`content`, `embedding`, `metadata`). The `simple` text-search
configuration (no language-specific stemming) is the right default for
multilingual content — English ticket IDs (`TOI-4521`), version
strings (`v8.4`), Hindi tokens, Tamil tokens all become searchable
exact-match tokens. Trade-off: changing the configuration (e.g. to
`english` for stemming) requires `ALTER TABLE` and a re-index, not
just a code change. Acceptable; we'd only switch if retrieval quality
showed a clear win.

---

## ADR-025 — Alembic owns schema changes; bootstrap_schema.py is a thin wrapper

**Context.** Before this ADR, the schema was created by
`scripts/bootstrap_schema.py` calling `Base.metadata.create_all()`.
That works exactly once: the first time it runs against an empty
database. It cannot add a column, drop a constraint, rename a table,
or do anything else to an existing schema — it silently no-ops. The
first time we need to change the schema on a database that has data
(prod, staging, dev with a long-running DB), there is no safe path.
Manual `ALTER TABLE` is the alternative, with no record of what was
applied where.

**Decision.** Adopt Alembic as the schema-change tool. The setup:

- Alembic is configured in `alembic.ini` and `migrations/env.py`.
- `migrations/env.py` reads the database URL from the same env var the
  app uses (`SUPPORT_AUTOMATION_DATABASE_URL`) and uses
  `Base.metadata` from `adapters/persistence/orm_models.py` as the
  source of truth for autogenerate.
- The baseline migration `migrations/versions/0001_initial_baseline.py`
  captures the full current schema as `op.create_table(...)` and
  `op.create_index(...)` calls. The matching `downgrade()` drops
  everything. A `CREATE EXTENSION IF NOT EXISTS vector` runs first so
  pgvector columns work on a fresh database.
- The pre-existing Postgres database was stamped at `0001` via
  `alembic stamp head` so it does not try to re-create tables it
  already has. Data is untouched.
- `scripts/bootstrap_schema.py` is now a thin wrapper around
  `alembic upgrade head`. Same command, same external behaviour;
  Alembic underneath.

**Why a baseline migration (vs. an empty marker):**
An empty baseline plus stamp would work for the existing database, but
would leave fresh databases (CI, new developer, replacement VM) with
no way to construct the schema via Alembic. A real CREATE TABLE
baseline means `alembic upgrade head` on a brand-new database produces
exactly the same schema as the live system.

**Consequences.**

- **Schema changes are tracked.** Every change lives in a numbered file
  under `migrations/versions/`, reviewable in PRs.
- **Schema changes are reversible.** Each migration's `downgrade()`
  function rolls it back; `alembic downgrade -1` is the escape hatch.
- **Schema state is queryable.** `alembic current` tells you which
  migration any database is at; `alembic_version` is a one-row table
  in the database itself.
- **No code outside `scripts/bootstrap_schema.py` and the new
  `migrations/` tree changed.** ORM models, repositories, use cases,
  API, dashboard — all untouched. `Base.metadata.create_all()` is no
  longer called by application code, but the integration test
  conftest still uses it for `*_test`-suffixed throwaway databases
  (which is the right call — those databases live for the duration of
  one pytest invocation; there's nothing to migrate).
- **One extra dependency** (`alembic>=1.13`, already in
  `pyproject.toml`).
- **Operators have one new command to remember**: `alembic revision
  --autogenerate -m "what changed"` to generate, then `alembic
  upgrade head` to apply. `bootstrap_schema.py` continues to work for
  the common case.

The full operator workflow lives in `docs/HANDBOOK.md` — "Changing the
schema".

---

## ADR-024 — Audit log lives at the outermost ring, not inside use cases

**Context.** Phase 1h opened with the question "how do we know what the
system did?" Without an audit trail, support staff have no way to
answer the manager who asks "why was that spike alerted at 2 am?", and
the system has no story for the compliance officer who will eventually
ask "show me every reply that went out in Q2 and what facts grounded
it." Phases 1a-1g produced data; phase 1h's first piece is the record
of *actions taken*.

**Decision.** Add a single append-only `audit_log` table, a single port
(`AuditLogRepositoryPort` with `add()` and `list_recent()`), in-memory
and Postgres implementations, and one `GET /api/audit` endpoint. The
load-bearing design choice is **where the audit log is written from**:

| Layer | Writes to audit log? | Why |
|---|---|---|
| `domain/` | No | Pure types. Stays decoupled from any side effects. |
| `service_layer/use_cases/` | **No** | Use cases stay testable with zero new dependencies. None of the existing 95 unit tests change. |
| `adapters/` | No | Repositories and source adapters don't know audit exists. |
| `entrypoints/cli/` | **Yes** | This is where the lifecycle boundary is observable: a cron run has a clear start and a clear finish, with result counts available at the end. |
| `entrypoints/web_api/` (future) | **Yes** | Same reasoning — the API layer is where requests have an observable boundary. |

The wrapper that does the writing — `entrypoints/cli/audit_helper.py` —
is a 30-line context manager. Each CLI gets ~5 new lines (the `with
cron_audit(...) as audit:` block) and a dict update for the result
counts. Business logic doesn't change in any file.

Shape of `AuditLogEntry`:

```python
actor: str          # "draft-replies", "ingest-feedback", "send-digest-daily", "api"
action: str         # "<actor>.started" | "<actor>.finished" | "<actor>.failed" | "<entity>.<verb>"
entity_type: str | None
entity_id: UUID | None
details: dict       # free-form: counts, language model name, recipient list, error message
occurred_at: datetime
```

`details` is deliberately a free-form `JSONB` column. Each call site
records different metadata; we don't want a schema migration every time
a new field becomes interesting. The dashboard renders it as key/value
pairs.

**Consequences.**

- The system can now answer forensic questions in seconds: "what did
  draft-replies do yesterday?" is `actor=draft-replies` filtered to a
  day; the Audit Log page in the dashboard exposes this directly.
- The audit trail is **append-only**. The port has no update or delete
  method, and the Postgres adapter exposes neither. Editable audit
  trails aren't audit trails.
- Disabling the audit log is a one-line change in each CLI (comment out
  the `with cron_audit(...)` block). Use cases keep working, tests keep
  passing.
- One new table; no changes to existing tables; no schema migration
  needed for any existing data. `bootstrap_schema.py` picks it up via
  `Base.metadata.create_all()` (idempotent).
- Web UI gets a sixth page (`/audit`). Outside `web_ui/`, the only
  files touched by this whole change are: domain entity, port,
  in-memory adapter, Postgres adapter, ORM addition, composition root,
  Depends factory, audit router + schema, CLI helper, the six cron
  CLIs (each ~5 lines), and the docs. No existing test breaks.

Future work (later in 1h): the API surface should also write audit
rows for sensitive reads — e.g., when a draft is fetched for review.
For phase 1 the cron side is what carries the audit weight.

---

## ADR-023 — Dashboard UI lives in `web_ui/` as a swappable React app

**Context.** Support staff need a place to look at the data the cron
jobs have produced — feedback, drafts, spikes, knowledge-base health,
analytics. Phase 1f closed the read-only JSON API; phase 1g closes the
visual gap. The user's explicit constraint at the start of this sprint:
"the UI should live in one folder and be easily replaceable" — a
property that was already designed into the broader plan but had not yet
been enforced in code.

**Decision.** Build the dashboard as a Vite + React 18 + TypeScript
single-page app inside `web_ui/` and enforce these isolation properties:

| Property | Mechanism |
|---|---|
| All UI code in one folder | Everything ships under `web_ui/`. Python has zero `.ts/.tsx/.css` files. |
| No Python imports from the UI | `web_ui/` is a separate npm project with its own `package.json`. Python never reads its source. |
| One coupling point | `entrypoints/web_api/static_mount.py` (~30 lines) — the only Python module that knows the SPA exists. Called from one line in `main.py`. |
| Removal recipe | `rm -rf web_ui/` plus commenting out the `mount_web_ui(app)` line in `main.py`. JSON API and cron CLIs keep working. |
| CI enforces it | `make ci-headless` moves `web_ui/` aside, runs the unit suite, restores `web_ui/`. Has to keep passing. |
| API is the contract | UI talks to the backend exclusively through `/api/...`. TypeScript types are auto-generated from `/api/openapi.json` via `openapi-typescript`. |

Tech stack:
- **Vite** for build / dev server (`npm run dev` + `npm run build`).
- **React 18 + TypeScript** for the UI framework.
- **TanStack Query** for server-state caching + auto-refresh polling.
- **React Router v6** for client-side routing across the five pages.
- **Tailwind CSS** for utility-first styling.
- **shadcn/ui** — components vendored into `src/components/ui/`
  (copy-paste, not an npm dep) so we have zero black-box UI primitives.
- **Recharts** for the analytics page.
- **openapi-typescript** to keep request / response types in lockstep
  with the FastAPI schemas via `npm run gen:api`.

Five pages: Inbox, Drafts, Spikes, Knowledge, Analytics. Auto-refresh
intervals per page (30 s / 30 s / 30 s / 60 s / 5 min) match the plan.
Audit log is deferred to phase 1h alongside the `audit_log` table.

**Consequences.** Two `Makefile` targets do the right thing for both
operators and CI:

- `make build` runs `pip install -e .[dev]` and `cd web_ui && npm ci && npm run build` in sequence. End state: a working FastAPI process that serves the SPA at `/` and the JSON API at `/api/...`.
- `make build-web` builds only the SPA — useful when iterating on the dashboard without touching Python.

The SPA bundle is ~790 KB minified (~240 KB gzipped) for the first cut,
mostly Recharts. Acceptable for an internal dashboard accessed over the
LAN; if we ship to public infrastructure later we'll code-split the
analytics page.

Operator caveats noted during install (all worked around inline; no
code changes needed):
- Corporate TLS inspection blocked `ui.shadcn.com`. Fix: run npm/npx
  with `NODE_OPTIONS="--use-system-ca"` (Node 22 picks up the corporate
  CA bundle that's installed for `curl`). Build-web target sets this
  automatically.
- React 19 has peer-dep conflicts with several packages (Recharts,
  openapi-typescript). Fix: `npm ci --legacy-peer-deps`. Same fix is
  applied in the build target.

If `web_ui/` ever stops being separable, the contract starts leaking.
Two checks catch that: a reviewer notices a cross-folder import, or
`make ci-headless` exits non-zero. Run it on every PR.

---

## ADR-022 — Draft replies are customer-facing copy, not internal status updates

**Context.** First end-to-end drafts produced by the phase-1d drafter
read like internal incident reports. A real Google Play review about ET
market data lag came back with five quality problems in a single body:

  1. Engineering jargon leaked through verbatim from internal Confluence
     ("the market data caching layer in app v5.7.x isn't always flushing
     when upstream quotes update").
  2. Internal JIRA identifiers ("tracked as ET-2010") appeared in the
     body, meaningful to our team and useless to the user.
  3. Release-process commentary ("we'll get it out as soon as it's
     validated") added words the user could not act on.
  4. Inline citation markers like `[1][3]` appeared in the body, because
     the original prompt instructed the language model to attribute
     claims inline. To support staff these were audit markers; to the
     user they looked like a half-finished email.
  5. The close was an open-ended ask ("please reply here and we'll dig
     in further"), pushing more work onto an already-frustrated user.

The root cause was singular: the prompt template treated the draft as
**internal communication that happens to be addressed to a user**,
instead of **a customer-facing email that happens to be informed by
internal facts**.

**Decision.** The drafter prompt (`prompts/draft_reply.md`) carries
explicit rules — what NOT to do, not just what to do:

  - Forbid internal jargon vocabulary in the body (`regression`,
    `caching layer`, `validated`, `tracked as`, internal IDs, etc.).
  - Forbid inline citation tags (`[1]`, `[2]`) in the body. Citation
    tracking happens through the structured `cited_chunk_indices` field
    only; support staff see the citation list beside the draft, the
    user never does.
  - Forbid process commentary the user can't act on ("our team is
    actively working on this") — replace with a concrete date / version
    or omit.
  - Forbid friction-inducing closes ("reply if you keep seeing this");
    end with a warm, brief sign-off.
  - Cap reply length at 130 words.

The numbered facts retrieved from the knowledge base remain unchanged
in the prompt — the language model still sees the same internal context,
including JIRA IDs and engineering details. The discipline is at the
output stage: paraphrase before it reaches the user.

**Consequences.** Drafts are sendable as-is or with a 30-second human
edit, which is what the support team needs. Trade-off: the prompt is
longer (~95 lines vs ~63), which costs marginal language-model tokens.
That cost is paid back many times over by support staff not having to
rewrite every draft.

Operational note: the recorded LLM response fixtures
(`data_fixtures/language_model_responses/`) cover classification only,
not drafting, so this prompt change did not break recorded-mode tests.
A future change to the drafter prompt that affects test behaviour
should be re-recorded via `scripts/record_llm_responses.py`.

---

## ADR-021 — JSON API docs use locally-bundled Swagger UI (no CDN)

**Context.** FastAPI's default `/api/docs` page generates HTML that
loads Swagger UI's JavaScript and CSS from a public CDN
(`cdn.jsdelivr.net`) at runtime. On the user's corporate network
(Times Internet) that CDN is blocked — the page loads but hangs
indefinitely with a blank screen, waiting for assets that never
arrive.

**Decision.** Use `fastapi-offline.FastAPIOffline` instead of the
standard `fastapi.FastAPI` in `entrypoints/web_api/main.py`. The
package is a drop-in replacement that bundles Swagger UI and ReDoc
as Python package data and serves them from a `/static-offline-docs/`
route on the FastAPI process itself. All HTTP behaviour, OpenAPI
generation, and dependency injection are identical to plain FastAPI
— only the docs-asset source changes.

**Consequences.** API docs work on any network with no firewall
allowlist needed. The trade-off is one extra dependency
(`fastapi-offline`) and ~750 KB of bundled Swagger UI assets in the
Python environment. Both are negligible. If the upstream package
goes stale, the fallback is straightforward: pin to the last working
version, or self-host the assets via `fastapi.staticfiles.StaticFiles`
pointing at a copy of `swagger-ui-dist`.

---

## How to add a new ADR

1. Pick the next number (ADR-026 at time of writing).
2. Write Context / Decision / Consequences. Aim for 5-12 lines per section.
3. Link it from the relevant section of `ARCHITECTURE.md` if it's structural.
4. If it supersedes an earlier decision, add a "Superseded by ADR-NNN" line
   to the older entry but **keep** the older entry — the historical
   reasoning matters.
