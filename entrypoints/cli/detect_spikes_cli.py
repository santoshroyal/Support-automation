"""Cron entrypoint: scan every cluster, record a spike event when one fires.

When running against Postgres the work runs inside a `cron_lock` so a slow
predecessor doesn't get trampled by the next scheduled run. The scheduling
cadence is typically every 30 minutes (the digest builder reads spike
events recorded since its last run).
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager, nullcontext
from typing import Iterator

from entrypoints.composition_root import build_app

_JOB_NAME = "detect-spikes"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect complaint-cluster spikes")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    args = parser.parse_args(argv)

    app = build_app()
    use_case = app.detect_complaint_spike()

    with _maybe_cron_lock(app.backend_name) as acquired:
        if acquired is False:
            print(f"[{_JOB_NAME}] previous run still in flight; skipping.", file=sys.stderr)
            return 0
        result = use_case.run()

    print(
        f"[detect_spikes] examined={result.clusters_examined} "
        f"spikes_recorded={result.spikes_recorded} "
        f"suppressed_recent={result.suppressed_recent} "
        f"(backend={app.backend_name})"
    )
    return 0


@contextmanager
def _maybe_cron_lock(backend_name: str) -> Iterator[bool | None]:
    if backend_name == "postgres":
        from adapters.persistence.cron_lock import cron_lock

        with cron_lock(_JOB_NAME) as acquired:
            yield acquired
        return

    with nullcontext():
        yield None


if __name__ == "__main__":
    sys.exit(main())
