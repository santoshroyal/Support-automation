"""Create the database schema for the support automation system.

Idempotent — running it again is safe; SQLAlchemy's `create_all()` skips
tables that already exist.

Reads `SUPPORT_AUTOMATION_DATABASE_URL` from the environment. Run from the
project root:

    .venv/bin/python scripts/bootstrap_schema.py

Use this instead of crafting an inline `python -c "..."` invocation —
shells routinely break long one-liners across lines and split string
literals mid-quote.
"""

from __future__ import annotations

import sys
from pathlib import Path

# When this script is run directly (`python scripts/bootstrap_schema.py`),
# only `scripts/` is on the import path. Add the project root so
# top-level packages like `adapters/`, `config.py`, etc., resolve.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from adapters.persistence.database import get_engine  # noqa: E402
from adapters.persistence.orm_models import Base  # noqa: E402
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
    engine = get_engine()
    Base.metadata.create_all(engine)

    print("Schema is in place. Tables:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
