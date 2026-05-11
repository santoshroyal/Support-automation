# Data fixtures

Dummy data the system uses when any source is set to `mode = local`. The repo
ships with a small but representative set covering the cases the pipeline
needs to handle.

## Layout

```
data_fixtures/
├── feedback/
│   ├── gmail/        # *.json — one file per email
│   ├── play/         # *.json — Play Developer reviews shape
│   └── apple/        # *.json — App Store Connect customerReviews shape
├── knowledge/
│   ├── confluence/   # *.md  — Markdown body + YAML frontmatter
│   ├── jira/         # *.json — JIRA REST issue shape
│   └── sheets/       # *.csv — header row + data rows
└── language_model_responses/
    └── *.json        # recorded prompt → response pairs for deterministic CI
```

## Adding a new scenario

1. Pick the source folder.
2. Drop a file matching the existing schema (look at the sibling files).
3. Use a stable, descriptive filename (`crash_after_update_hindi.json`,
   not `email01.json`) — fixtures are read in sorted order.
4. If the scenario should produce a specific draft, add a corresponding
   `language_model_responses/` entry so CI is deterministic.

## Schemas

### Gmail (`feedback/gmail/*.json`)

```json
{
  "external_id": "msg_abc123",
  "thread_id": "thread_xyz",
  "from": "user@example.com",
  "subject": "App keeps crashing",
  "body": "...",
  "received_at": "2026-04-30T11:30:00Z",
  "language_hint": "en",
  "app_version": "8.3.1",
  "device": "Pixel 7"
}
```

`from` is what the user typed in the From header. `language_hint` is optional
— the language detector overrides it if present.

(Schemas for `play/`, `apple/`, `confluence/`, `jira/`, `sheets/` arrive with
their respective adapters.)
