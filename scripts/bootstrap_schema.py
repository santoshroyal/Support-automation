"""Bring the database schema up to the latest version via Alembic.

This is the single command that gets a database ready to run the
support-automation system. Behaviour by database state:

  - Empty database → runs every migration from 0001 onwards.
  - Already at the latest migration → no-op.
  - Behind by one or more migrations → applies just the missing ones.

Same external interface as before — `python scripts/bootstrap_schema.py`
— but the implementation now goes through Alembic instead of
`Base.metadata.create_all()`. Why the change: `create_all` only creates
tables that don't yet exist; it can't alter or drop. With Alembic,
schema changes are reviewable, reversible, and tracked in
`migrations/versions/`. See ADR-025.

If you've changed an ORM model and want to generate a new migration:

    .venv/bin/alembic revision --autogenerate -m "short description"

…then review the generated file in `migrations/versions/`, commit it,
and re-run this script.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import get_config  # noqa: E402


def main() -> int:
    config = get_config()
    if not config.use_postgres():
        print(
            "ERROR: SUPPORT_AUTOMATION_DATABASE_URL is not set.",
            file=sys.stderr,
        )
        print(
            "Export it first, for example:\n"
            "  export SUPPORT_AUTOMATION_DATABASE_URL="
            "postgresql+psycopg://$USER@localhost/support_automation_local",
            file=sys.stderr,
        )
        return 1

    print(f"Connecting to: {config.database_url}")
    print("Running: alembic upgrade head")

    # Resolve the venv's alembic so this works regardless of the active shell.
    alembic_bin = _PROJECT_ROOT / ".venv" / "bin" / "alembic"
    command = [str(alembic_bin) if alembic_bin.exists() else "alembic", "upgrade", "head"]

    completed = subprocess.run(command, cwd=_PROJECT_ROOT)
    if completed.returncode != 0:
        print("alembic upgrade head failed", file=sys.stderr)
        return completed.returncode

    print("Schema is at the latest migration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
