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

1. Pick the next number (ADR-023 at time of writing).
2. Write Context / Decision / Consequences. Aim for 5-12 lines per section.
3. Link it from the relevant section of `ARCHITECTURE.md` if it's structural.
4. If it supersedes an earlier decision, add a "Superseded by ADR-NNN" line
   to the older entry but **keep** the older entry — the historical
   reasoning matters.
