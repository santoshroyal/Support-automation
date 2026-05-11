"""Cron entrypoint: pull new feedback from every (app × channel) source.

When running against Postgres, the work is wrapped in a `cron_lock` so a
slow predecessor never gets trampled by the next scheduled run. Against
the in-memory backend the lock is a no-op (the in-memory case is
single-process anyway).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from contextlib import contextmanager, nullcontext
from typing import Iterator

from entrypoints.composition_root import build_app
from service_layer.use_cases.ingest_feedback import IngestFeedbackResult

_JOB_NAME = "ingest-feedback"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest feedback from configured sources")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit (cron mode)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result JSON")
    args = parser.parse_args(argv)

    app = build_app()
    use_case = app.ingest_feedback()

    with _maybe_cron_lock(app.backend_name) as acquired:
        if acquired is False:
            print(f"[{_JOB_NAME}] previous run still in flight; skipping.", file=sys.stderr)
            return 0
        results = use_case.run()

    if args.json:
        _print_json(results)
    else:
        _print_human(results)
    return 0


@contextmanager
def _maybe_cron_lock(backend_name: str) -> Iterator[bool | None]:
    """Acquire a cron advisory lock when running against Postgres; no-op otherwise.

    Yields True if acquired, False if a peer holds it, None when the
    backend doesn't need a lock (e.g. in-memory tests).
    """
    if backend_name == "postgres":
        from adapters.persistence.cron_lock import cron_lock

        with cron_lock(_JOB_NAME) as acquired:
            yield acquired
        return

    with nullcontext():
        yield None


def _print_json(results: list[IngestFeedbackResult]) -> None:
    grouped: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for result in results:
        grouped[result.app_slug][result.channel.value] = {
            "fetched": result.fetched,
            "inserted": result.inserted,
            "duplicates": result.duplicates,
        }
    print(json.dumps(grouped, indent=2, sort_keys=True))


def _print_human(results: list[IngestFeedbackResult]) -> None:
    by_app: dict[str, list[IngestFeedbackResult]] = defaultdict(list)
    for result in results:
        by_app[result.app_slug].append(result)

    totals = {"fetched": 0, "inserted": 0, "duplicates": 0}
    for app_slug in sorted(by_app):
        print(f"[{app_slug}]")
        for result in by_app[app_slug]:
            print(
                f"  {result.channel.value:<18} "
                f"fetched={result.fetched:<3} "
                f"inserted={result.inserted:<3} "
                f"duplicates={result.duplicates:<3}"
            )
            totals["fetched"] += result.fetched
            totals["inserted"] += result.inserted
            totals["duplicates"] += result.duplicates

    print(
        f"[total] fetched={totals['fetched']} "
        f"inserted={totals['inserted']} "
        f"duplicates={totals['duplicates']}"
    )


if __name__ == "__main__":
    sys.exit(main())
