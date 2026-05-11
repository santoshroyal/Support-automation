# Secrets

This directory holds real credentials. **It is gitignored.** The repo never contains any of the files below; the operator places them on the production VM.

For local development, leave this directory empty — every external source has a `local_*` adapter that reads from `data_fixtures/` instead. See [`docs/HANDBOOK.md`](../docs/HANDBOOK.md) for going live with each source.

## Expected files (when running in real mode)

| File | Source | How to obtain |
|---|---|---|
| `gmail.json` | Gmail | Google Cloud Console → APIs & Services → Credentials → Create OAuth 2.0 client ID (*Desktop app*). Download JSON. |
| `gmail_token.json` | Gmail | Auto-generated on first run by `python scripts/gmail_oauth_setup.py`. |
| `play_service_account.json` | Google Play Console | Play Console → Setup → API access → Create service account → Download JSON key. |
| `app_store.p8` | Apple App Store Connect | App Store Connect → Users and Access → Keys → Generate API key (App Manager role). |
| `atlassian_token` | Confluence + JIRA | Atlassian → User settings → API tokens → Create token. Single-line text file. |
| `smtp_password` | Outbound digest email | From your SMTP provider (e.g. Google Workspace app password). Single-line text file. |

## Permissions

```bash
chmod 600 secrets/*
chown <systemd-service-user> secrets/*
```

## Rotation

- Atlassian + SMTP credentials: rotate every 90 days.
- Service-account keys: rotate yearly.
- App Store Connect keys: rotate yearly.
