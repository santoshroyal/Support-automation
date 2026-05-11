"""Read-only JSON API for the support-automation dashboard.

Per ADR-006, dashboard users are consumers only — no write endpoints
exist. Every route is GET. Settings, thresholds, and prompt edits stay
engineer-managed in YAML / Markdown under `config_files/` and `prompts/`.

Module layout:

    main.py            FastAPI app factory + router registration
    dependencies.py    Depends() factories that pull repositories
                       and use cases from the composition root
    error_handlers.py  Domain exception → HTTP status mapping
    routers/           One file per resource (health, apps, feedback, …)
    schemas/           Pydantic response models per resource
    static_mount.py    The ONE line that serves the React build —
                       remove it (plus web_ui/) to drop the UI
"""
