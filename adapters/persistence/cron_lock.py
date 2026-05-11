"""Advisory-lock helper for cron entry-points.

When a cron job's previous run is still in flight (e.g. an ingest pass that
took longer than its 15-minute schedule), we don't want a second instance
starting on top of it. PostgreSQL advisory locks give us a session-scoped
mutex without any rows to manage:

    with cron_lock("ingest-feedback") as acquired:
        if not acquired:
            print("Previous run still in flight; skipping.")
            return
        # do the work

`pg_try_advisory_lock` is non-blocking — if another session already holds
the lock, the call returns False immediately. The lock auto-releases when
the connection closes (we explicitly release on the way out for tidiness).

Why a dedicated AUTOCOMMIT engine: the lock connection sits idle while the
cron job does its actual work (which may take many minutes when calling
LLMs). In the default isolation level, that idle time counts against
`idle_in_transaction_session_timeout`, and PostgreSQL would terminate the
connection — preventing the explicit release. Using a sub-engine derived
with `execution_options(isolation_level="AUTOCOMMIT")` ensures every
connection it hands out starts and stays out of a transaction.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text

from adapters.persistence.database import get_engine


@contextmanager
def cron_lock(job_name: str) -> Iterator[bool]:
    """Yield True if we acquired the lock, False if a peer already holds it.

    The caller decides what to do on False (typically log + exit). The lock
    is released on context exit regardless of outcome.
    """
    engine = get_engine().execution_options(isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:job_name))"),
                {"job_name": job_name},
            ).scalar()
        )
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:job_name))"),
                    {"job_name": job_name},
                )
