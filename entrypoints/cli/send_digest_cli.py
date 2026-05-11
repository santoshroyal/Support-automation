"""Cron entrypoint: build and send the hourly or daily stakeholder digest.

Example schedules from `deployment/systemd/`:
  * hourly  → every hour, type=hourly
  * daily   → 08:00 IST, type=daily

When running against Postgres the work runs inside a `cron_lock` so two
overlapping runs of the same digest type are impossible. The default
notification sender is `LocalEmailSender` — write digests to disk for the
operator to inspect during the first 24-48 hours, then flip to SMTP.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager, nullcontext
from typing import Iterator

from entrypoints.composition_root import build_app

_VALID_TYPES = ("hourly", "daily")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send the stakeholder digest email")
    parser.add_argument("--type", choices=_VALID_TYPES, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)

    app = build_app()
    use_case = app.send_stakeholder_digest(digest_type=args.type)
    job_name = f"send-digest-{args.type}"

    with _maybe_cron_lock(app.backend_name, job_name) as acquired:
        if acquired is False:
            print(f"[{job_name}] previous run still in flight; skipping.", file=sys.stderr)
            return 0
        result = use_case.run()

    print(
        f"[send_digest:{result.digest_type}] "
        f"spikes_in_window={result.spikes_in_window} "
        f"recipients={result.recipients} "
        f"sent={result.sent} "
        f"error={result.error or 'none'} "
        f"(sender={app.notification_sender.name}, backend={app.backend_name})"
    )
    return 0 if result.sent else 1


@contextmanager
def _maybe_cron_lock(backend_name: str, job_name: str) -> Iterator[bool | None]:
    if backend_name == "postgres":
        from adapters.persistence.cron_lock import cron_lock

        with cron_lock(job_name) as acquired:
            yield acquired
        return

    with nullcontext():
        yield None


if __name__ == "__main__":
    sys.exit(main())
