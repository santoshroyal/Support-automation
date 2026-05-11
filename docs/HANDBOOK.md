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

- [ ] All credentials placed in `secrets/`; `scripts/verify_credentials.py`
      returns ✓ for every source.
- [ ] `GET /api/health` (when phase 1f ships) returns 200 with all sources green.
- [ ] System has run for ≥ 24 hours with `notification.mode = local` —
      digests written to disk, reviewed by a human for accuracy.
- [ ] Spike thresholds tuned in `config_files/thresholds.yaml`. The
      defaults (`min_count=2`, `ratio=2.0`) are aggressive for fixture
      volumes; production volumes typically warrant `min_count=5`,
      `ratio=3.0`.
- [ ] Stakeholder email list reviewed in
      `config_files/stakeholders.yaml`.
- [ ] Prompt templates reviewed (`prompts/classify_feedback.md`, plus
      future `prompts/draft_reply.md`).
- [ ] Daily monitoring rhythm agreed: someone checks `digest_log` and
      (later) `audit_log` daily for the first 2 weeks.
- [ ] Then flip `notification.mode = "real"`.

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
