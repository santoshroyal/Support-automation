# Operations Handbook

How an operator brings real data sources online, in the order it's
typically done. Each section ends with a `mode = real` flip in the
relevant config file.

For *why* the system is built this way, see
[`DECISIONS.md`](DECISIONS.md). For *what* lives where, see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## The default state on a fresh install

Everything starts in **local mode**. The pipeline runs end-to-end against
fixture files in `data_fixtures/`. No real credentials anywhere. No
emails sent. Nothing posted to Play or App Store consoles.

That's intentional — you should be able to:

```bash
make setup-postgres
.venv/bin/pip install -e ".[dev]"
.venv/bin/python scripts/bootstrap_schema.py
.venv/bin/python -m entrypoints.cli.ingest_feedback_cli --once
.venv/bin/python -m entrypoints.cli.classify_and_cluster_cli --once
.venv/bin/python -m entrypoints.cli.sync_knowledge_base_cli --once
.venv/bin/python -m entrypoints.cli.detect_spikes_cli --once
.venv/bin/python -m entrypoints.cli.send_digest_cli --type=daily --once
ls var/log/digests/
```

…and see a digest HTML file produced from fixtures, with zero
credentials configured. Only when you've reviewed the system's behavior
end-to-end on fixtures should you flip individual sources to real mode.

## A. Gmail — read user-feedback emails and write reply drafts

1. Pick a Google Cloud project (or create one). Enable the Gmail API
   under **APIs & Services → Library**.
2. Under **APIs & Services → Credentials**, **Create OAuth 2.0 Client
   ID** with application type *Desktop app*. Download the JSON.
3. Save it as `secrets/gmail.json`. Permission: `chmod 600`.
4. Configure scopes: `https://www.googleapis.com/auth/gmail.modify`
   (read + write drafts).
5. Decide the feedback inbox (typically a shared mailbox like
   `support@timesofindia.com`). Create a Gmail filter that labels
   incoming user feedback with `support-feedback`.
6. Run `python scripts/gmail_oauth_setup.py` (planned helper). It opens
   the browser, completes OAuth, and saves `secrets/gmail_token.json`.
7. In `config_files/feedback_sources.yaml`:
   ```yaml
   gmail:
     mode: real
     label: support-feedback
   ```
8. Verify: `python scripts/verify_credentials.py --source gmail`
   (planned helper) should return ✓.

## B. Google Play Console — read Android reviews

1. **Google Play Console → Setup → API access**. Link to a Google Cloud
   project (can be the same as Gmail's).
2. Create a **service account**. Grant the role *"Reply to reviews"* in
   Play Console (this also grants read).
3. Download the service-account JSON key → save as
   `secrets/play_service_account.json`. `chmod 600`.
4. In `config_files/feedback_sources.yaml`:
   ```yaml
   play:
     mode: real
     # The package name comes from config_files/apps.yaml per-app.
   ```
5. Note: the Play Developer API only returns reviews from the **last 7
   days**. Backfill is impossible — the system starts capturing from
   the moment you flip `mode=real`.

## C. Apple App Store Connect — read iOS reviews

1. **App Store Connect → Users and Access → Keys → API Keys**.
2. Generate a new key with *App Manager* role. Download the `.p8` file
   (one-time download — save it immediately) → `secrets/app_store.p8`.
   `chmod 600`.
3. Note the **Key ID** and **Issuer ID** shown on the Keys page.
4. In `config_files/feedback_sources.yaml`:
   ```yaml
   apple:
     mode: real
     key_id: ABC123XYZ
     issuer_id: 11111111-2222-3333-4444-555555555555
     # bundle_id and app_id come from config_files/apps.yaml per-app.
   ```
5. The system uses JWT-signed requests; tokens are short-lived and
   minted per request.

## D. Confluence — read product / bug / release wiki pages

1. **Atlassian → User Settings → API tokens → Create token**. Copy and
   save to `secrets/atlassian_token` (single-line file). `chmod 600`.
2. In `config_files/knowledge_sources.yaml`:
   ```yaml
   confluence:
     mode: real
     base_url: https://timesinternet.atlassian.net/wiki
     username: ops@timesinternet.in
     space_keys: [TOI, ET, NBT, FAQ]
     label_filter: [public-support, release-notes]   # optional
   ```
3. Flip `mode = real`. The first sync may take 5-15 minutes depending
   on space size.

## E. JIRA — read live tickets, statuses, fix versions

1. Reuse the Atlassian token from D. (Same `secrets/atlassian_token`.)
2. In `config_files/knowledge_sources.yaml`:
   ```yaml
   jira:
     mode: real
     base_url: https://timesinternet.atlassian.net
     username: ops@timesinternet.in
     jql: "project IN (TOI, ET, NBT, BUG, MOBILE) AND updated > -30d"
   ```
3. Flip `mode = real`. The JQL controls scope; tune it to whatever
   subset of projects the support automation should consume.

## F. Google Sheets — read manually maintained trackers

1. Reuse the Play service account from B (or create a new one with
   Sheets API enabled).
2. **Share each tracker sheet** (View access) with the service-account
   email shown in the JSON key (`client_email` field).
3. In `config_files/knowledge_sources.yaml`:
   ```yaml
   sheets:
     mode: real
     - sheet_id: "1A2B3C…"
       tab_name: "Bug Tracker"
       columns_used: ["Bug ID", "Description", "Status", "ETA", "Owner"]
   ```
4. Flip `mode = real`.

## G. SMTP — actually send stakeholder digest emails

⚠️ **Don't do this on day 1.** Run the system for at least 24 hours
with `notification.mode = local`, review the HTML files in
`var/log/digests/`, and tune `config_files/thresholds.yaml` until the
digest fires on the right things and stays quiet on the wrong things.
Only then flip SMTP on.

1. Get SMTP credentials (server, port, username, password). Save
   password to `secrets/smtp_password` (single-line file). `chmod 600`.
2. In `config_files/notification.yaml` (planned):
   ```yaml
   notification:
     mode: real
     smtp:
       host: smtp.example.com
       port: 587
       username: support-automation@timesinternet.in
       from_address: support-automation@timesinternet.in
       use_tls: true
   ```
3. **Replace the dummy stakeholder addresses** in
   `config_files/stakeholders.yaml` with real ones before this flip:
   ```yaml
   stakeholders:
     - name: Engineering Lead
       email: real-eng-lead@timesinternet.in
       receives_hourly: true
       receives_daily: true
     # …
   ```
4. Restart the cron timers. Watch the next hourly digest land in
   stakeholders' inboxes.

## H. Language model (already done by default)

The Claude Code CLI is the primary; Codex and Ollama Gemma are
fallbacks; Recorded is the always-healthy final fallback. No setup is
typically needed if you can run `claude --version` from your shell.

To explicitly check:

```bash
claude --version          # should print a version
codex --version           # optional fallback
ollama list               # optional fallback; should show gemma3:latest if used
```

In `config_files/language_models.yaml`:

```yaml
chain:
  - kind: claude_code      # primary
  - kind: codex_cli        # fallback 1
  - kind: ollama_gemma     # fallback 2 (only if you've pulled the model)
  - kind: recorded         # always-healthy safety net
```

## Pre-flight checklist before going live with real stakeholders

This is the one-page list to walk through before flipping the first
source from `mode=local` to `mode=real`. The system has been running on
fixtures end-to-end for a while; this list is what stops the "we went
live and immediately spammed 50 stakeholders" class of failure.

### Infrastructure

- [ ] **Code is on the VM at `/opt/support-automation`** with the
      systemd user (`support-automation`) owning everything.
- [ ] **PostgreSQL 16 + pgvector** are installed and running locally
      on the VM. `psql -U support_automation -c "SELECT 1;"` succeeds
      under the service account.
- [ ] **Alembic schema is current.** `.venv/bin/alembic current`
      prints a real revision id (e.g. `0001 (head)`), not blank.
- [ ] **`/etc/support-automation/env`** is in place with the right
      `SUPPORT_AUTOMATION_DATABASE_URL`, mode flags for every source
      (still `local` everywhere at this stage), and 640 file perms
      owned by the service account.
- [ ] **All eight systemd units** are installed and enabled:
      `systemctl list-timers 'support-automation-*'` shows 7 timers
      with a `NEXT` column populated; the API service is `active
      (running)`.
- [ ] **`make ci-headless` passes locally** after a fresh `git pull`
      on the VM — proves the deployed code matches what's in version
      control.

### Health and observability

- [ ] **`GET /api/health` returns 200** with `status: "healthy"` and
      every check green (`database`, `language_model`,
      `embedding_model`).
- [ ] **Audit log has entries from every cron**. After one full hour
      of running, run:
      ```bash
      psql -c "SELECT actor, count(*) FROM audit_log WHERE occurred_at > now() - interval '2 hours' GROUP BY actor ORDER BY actor;"
      ```
      Every cron actor should appear at least once.
- [ ] **Dashboard Audit Log page** loads, populated, and refreshes.
      `http://127.0.0.1:8080/audit` over SSH tunnel.
- [ ] **journald has no repeated failures**:
      ```bash
      journalctl -t support-automation-failure --since "24 hours ago" | wc -l
      ```
      Should be 0.

### Content and configuration

- [ ] **Stakeholder email list reviewed** in
      `config_files/stakeholders.yaml`. Every address on the list is
      currently active and the right person to receive the digest.
- [ ] **Spike thresholds tuned** in `config_files/thresholds.yaml`.
      Defaults (`min_count=2`, `ratio=2.0`) are aggressive for fixture
      volumes — production typically wants `min_count=5`, `ratio=3.0`.
- [ ] **Prompt templates reviewed** by a human:
      - `prompts/classify_feedback.md`
      - `prompts/draft_reply.md` (post-ADR-022 — confirm tone rules
        still match current support-team voice)
- [ ] **Apps registry** in `config_files/apps.yaml` lists the apps
      you actually want to ingest from. Spelling matters — `app_slug`
      is a foreign-key-like identifier across feedback, drafts, and
      analytics.

### The 24-48-hour shadow run

- [ ] **Run for ≥ 24 h with `notification.mode = local`.** Digests
      are written to `/var/log/support-automation/digests/` as HTML
      files; a human opens at least 2 of them in a browser and
      confirms they read like what stakeholders should receive.
- [ ] **Inspect 5 random drafts** via the Drafts page. Confirm: no
      internal IDs leaked, no bracket citation markers, language matches
      the original feedback, body reads like something the support
      team would send.
- [ ] **Inspect any spike that fired**. Open the spike's
      drill-down; verify the sample feedbacks are genuinely related
      and that the ratio makes sense.

### People

- [ ] **On-call rotation agreed** — who reads `journalctl -t
      support-automation-failure` daily for the first 2 weeks?
- [ ] **The on-call person has read `docs/HANDBOOK.md` runbook
      section** ("When something breaks in production") and knows where
      it is.
- [ ] **Rollback plan agreed** — one named person can flip
      `notification.mode = local` if the live digest goes wrong (single
      env file edit + `systemctl restart 'support-automation-*.timer'`).

### Flip the switch

Only after every box above is ticked:

- [ ] Set the first source to `mode=real` in `/etc/support-automation/env`
      (typically Confluence or Sheets first — read-only and reversible).
- [ ] Restart timers: `sudo systemctl restart 'support-automation-*.timer'`.
- [ ] Watch the audit log + journald for one cron cycle.
- [ ] Repeat for the next source 24 h later if the previous flip held.
- [ ] `notification.mode = real` is the **last** flip — only after the
      digest output has been reviewed across at least one weekend.

## Rollback to local mode

Any `*.mode = "local"` flip immediately switches that source back to
fixtures on the next cron tick. Useful when:

- A credential rotates or expires — system stays alive on fixtures
  while you rotate the key.
- An upstream API breaks (Gmail outage, JIRA migration) — drafts keep
  flowing from the last fixture set instead of the cron failing.
- You're doing a controlled demo without touching production data.

There's no need to "un-deploy" anything — just edit the YAML, save,
and the next cron run picks it up.

## Secrets hygiene

- `secrets/` is `.gitignore`d. The repo never contains real credentials.
- File permissions on the VM: `chmod 600 secrets/*` and `chown` to the
  systemd service user (typically `support-automation`).
- Rotate Atlassian and SMTP credentials every 90 days.
- Rotate service-account keys yearly.
- `secrets/README.md` lists every expected file and what populates it.

If a secret leaks (committed accidentally, posted in chat, etc.):

1. Revoke immediately at the source (Atlassian token revocation, etc.).
2. Generate a new credential.
3. Replace `secrets/<file>` on the VM.
4. Restart the cron timers (`systemctl restart 'support-automation-*.timer'`).

---

## Changing the database schema (Alembic)

The schema is owned by Alembic (ADR-025). The ORM models in
`adapters/persistence/orm_models.py` are the source of truth; Alembic
diffs them against the live database to produce numbered migrations
under `migrations/versions/`. Every migration has an `upgrade()` and a
`downgrade()` — schema changes are reviewable in PRs and reversible at
runtime.

### Common workflow — add or change a column

```bash
# 1. Edit the ORM model in adapters/persistence/orm_models.py.
#    Example: add `country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)`
#    to FeedbackOrm.

# 2. Make sure the database you're pointed at is at the current head.
export SUPPORT_AUTOMATION_DATABASE_URL=postgresql+psycopg://$USER@localhost/support_automation_local
.venv/bin/alembic current     # expect a clean revision id

# 3. Generate the migration. Alembic compares your ORM change to the DB.
.venv/bin/alembic revision --autogenerate -m "add country_code to feedback"

# 4. **Review the generated file** under migrations/versions/.
#    Autogenerate is good but not perfect — column renames look like
#    drop + add; check the upgrade() and downgrade() both make sense.
#    Commit the file when you're happy.

# 5. Apply it.
.venv/bin/alembic upgrade head

# 6. Verify.
psql -d support_automation_local -c "\d feedback"
```

### Rollback

```bash
.venv/bin/alembic downgrade -1   # roll back the most recent migration
.venv/bin/alembic downgrade <revision-id>   # roll back to a specific revision
```

The downgrade is only as good as the migration's `downgrade()` function
— review the autogenerated downgrade when you create the migration.

### Useful commands

```bash
alembic current                        # show current revision of the connected DB
alembic history                        # show the linear migration history
alembic upgrade head                   # apply all pending migrations
alembic upgrade +1                     # apply one migration
alembic downgrade -1                   # roll back one migration
alembic stamp head                     # mark current state as up-to-date WITHOUT running anything
                                       # (use when bootstrapping a DB whose schema was created another way)
```

### What's NOT covered by Alembic

- The in-memory backend tests. They don't talk to Alembic at all —
  they use plain Python objects. `make ci-headless` keeps passing.
- The Postgres integration tests. They create their own
  `*_test`-suffixed throwaway database fresh on every pytest run via
  `Base.metadata.create_all()`. Single-run lifetime; nothing to
  migrate.
- Data migrations (e.g. "rename all feedbacks where app_slug='x' to
  'y'"). Alembic supports them via `op.execute("UPDATE …")`, but
  phase 1 hasn't needed any; the pattern would be added when the
  first data-migration is actually required.

### When something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `alembic upgrade head` says "Target database is not up to date." | A migration applied partially and rolled back. | `alembic current` to see where you are; resolve manually if the DB has half-applied DDL. |
| Autogenerate produced an empty migration | The ORM model and DB are already in sync; you forgot to edit the ORM. | Edit `orm_models.py` first, then re-run autogenerate. |
| Autogenerate produced a migration that drops tables you want to keep | You ran autogenerate against the wrong database. | Discard the generated file, point `SUPPORT_AUTOMATION_DATABASE_URL` at the right database, re-run. |
| Alembic complains about pgvector types | `pgvector` Python package not installed in the venv. | `.venv/bin/pip install pgvector` — already a project dep, this only happens if the venv drifted. |

---

## When something breaks in production (runbook)

The system runs unattended on the VM. When you're paged or notice
something off, work through the relevant section below. Each one is
diagnose → fix → verify.

### 1. The API isn't responding

**Diagnose:**
```bash
# Is the service actually up?
sudo systemctl status support-automation-api.service

# What did it last say?
journalctl -u support-automation-api.service --since "30 minutes ago" -n 200

# Can the process see the database?
curl -s http://127.0.0.1:8080/api/health
```

**Likely causes + fixes:**

| What you see | Cause | Fix |
|---|---|---|
| `Active: failed (Result: exit-code)` | Postgres unreachable, env file missing, or port already taken | Read the last error lines from journalctl; usually the cause is right there. |
| `/api/health` returns 200 but says `database` unhealthy | Postgres down, or the `SUPPORT_AUTOMATION_DATABASE_URL` is stale | `sudo systemctl status postgresql`; restart it if needed; check the env file |
| `/api/health` returns 200 but says `language_model` unhealthy | The `claude` / `codex` CLI auth expired on the service account | Switch language_model.primary to a working model in the env file; re-run support-automation-api.service |

**Verify:** `curl -s http://127.0.0.1:8080/api/health | jq '.status'` returns `"healthy"`.

---

### 2. A cron job is failing repeatedly

**Diagnose:**
```bash
# Find every failure tagged by the OnFailure handler:
journalctl -t support-automation-failure --since "24 hours ago"

# Read the failing cron's last run:
journalctl -u support-automation-draft.service -n 200 --no-pager

# How often did it run lately?
systemctl list-timers 'support-automation-*' --all
```

**Likely causes + fixes:**

| What you see | Cause | Fix |
|---|---|---|
| `cron_lock could not acquire lock` repeatedly | A previous run hung and never released its advisory lock | `psql -d support_automation -c "SELECT pg_advisory_unlock_all();"` from a fresh session, or restart Postgres |
| `subprocess.TimeoutExpired` on the language model | `claude` / `codex` CLI hanging | Verify `claude --version` works under the service user; failing that, downgrade the model in the env file |
| `psycopg.OperationalError: connection refused` | Postgres down | `sudo systemctl restart postgresql` |
| `Permission denied` on a fixture or secret | File mode wrong after a `git pull` | `sudo chown -R support-automation:support-automation /opt/support-automation /etc/support-automation` |

**Verify:** trigger the cron manually:
```bash
sudo systemctl start support-automation-draft.service
journalctl -u support-automation-draft.service -n 50 --no-pager
```
Look for `<actor>.finished` in the most recent log lines, or check the dashboard's Audit Log page.

---

### 3. The daily digest didn't send

**Diagnose:**
```bash
# Did the timer fire?
systemctl list-timers support-automation-digest-daily.timer --all
journalctl -u support-automation-digest-daily.service -n 100

# Did the service know who to send to?
psql -d support_automation -c "SELECT type, sent_at, recipients_jsonb, error FROM digest_log ORDER BY sent_at DESC LIMIT 5;"
```

**Likely causes + fixes:**

| What you see | Cause | Fix |
|---|---|---|
| Timer last triggered hours ago, not at 08:00 | Timezone mismatch between VM and the `Asia/Kolkata` specifier | Verify `timedatectl`; either set the VM TZ to IST or change the timer's `OnCalendar` to the UTC equivalent (02:30) |
| `digest_log.error` is `"smtp_unauthorized"` | SMTP password rotated | Replace `secrets/smtp_password` and restart the digest timer |
| `digest_log.recipients_jsonb` is `null` or `[]` | Stakeholder file is empty | Re-check `config_files/stakeholders.yaml`; the file is engineer-managed |
| No row in `digest_log` at all | The timer fired but the service exited before reaching the sender | Look at `journalctl -u support-automation-digest-daily.service -n 200` for the actual error |

**Verify:**
```bash
sudo systemctl start support-automation-digest-daily.service
ls -lt /var/log/support-automation/digests/ | head -5
```
Latest digest file should be from the last few minutes.

---

### 4. Disk is filling up

**Diagnose:**
```bash
df -h /
sudo du -sh /var/log/journal /var/log/support-automation /opt/support-automation/var
```

**Likely causes + fixes:**

| What you see | Cause | Fix |
|---|---|---|
| `/var/log/journal/...` is many GB | journald keeping logs forever | Edit `/etc/systemd/journald.conf`: set `SystemMaxUse=2G` and `MaxRetentionSec=30day`; `sudo systemctl restart systemd-journald` |
| `/var/log/support-automation/digests/` is huge | Notification mode is `local` and never flipped to `real` | Either flip to `real` or add a cron to delete files older than 30 d |
| `/opt/support-automation/var/support_automation/drafts/` is huge | Drafts have been written for months and never archived | Same: archive or delete files older than 30 d |
| Postgres data dir > 50% of disk | Audit log table growing unbounded | `psql -c "SELECT pg_size_pretty(pg_relation_size('audit_log'));"`; if needed, delete rows older than 90 d in the SQL prompt |

**Verify:** `df -h /` shows comfortable headroom (>20%).

---

### 5. Atlassian / SMTP / Play credentials expired

**Diagnose:**
```bash
journalctl -u support-automation-knowledge-sync.service -n 200 | grep -iE "401|403|unauthor"
```

**Fix:**

1. Regenerate the credential at the source (Atlassian → API tokens, SMTP provider, Play Console → API access).
2. Update the matching file under `secrets/` on the VM. `chmod 600` it.
3. Restart all timers so the next run picks up the new credential:
   ```bash
   sudo systemctl restart 'support-automation-*.timer'
   ```
4. Trigger one cron manually to confirm:
   ```bash
   sudo systemctl start support-automation-knowledge-sync.service
   ```

**Verify:** the knowledge-sync section of `/api/knowledge/sources` shows a fresh `latest_document_at` after the manual run.

---

### 6. The API returns a lot of 500s

**Diagnose:**
```bash
# Pull recent error logs:
journalctl -u support-automation-api.service --since "1 hour ago" | grep '"level": "ERROR"'

# Each 500 in the response carries a trace_id; grep journald for it:
journalctl -u support-automation-api.service | grep '<trace_id_from_response>'
```

**Likely causes + fixes:**

| What you see | Cause | Fix |
|---|---|---|
| Many `psycopg.OperationalError` | Postgres connection pool exhausted | Reduce dashboard polling interval, restart the API service, or bump `pool_size` in `adapters/persistence/database.py` |
| Many `KnowledgeRetrievalError` | pgvector extension dropped or HNSW index corrupted | `psql -c "REINDEX INDEX ix_knowledge_chunk_embedding_hnsw;"` |
| One specific trace_id repeats | A bug introduced by a recent deploy | Roll back the deploy or hotfix the specific route |

**Verify:** error rate drops to zero in journald grep output. Quick way:
```bash
journalctl -u support-automation-api.service --since "5 minutes ago" | grep -c '"level": "ERROR"'
```
Should be near zero on a healthy system.
