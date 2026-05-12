"""Cron entrypoint: pull updated docs from each knowledge source, chunk + embed, persist.

Typically scheduled every 90 minutes (Confluence/JIRA editorial pace);
the digest job depends only on the database state, not on this run, so a
slow knowledge sync never blocks the rest of the pipeline.

When running against Postgres the work runs inside a `cron_lock`.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager, nullcontext
from typing import Iterator

from entrypoints.cli.audit_helper import cron_audit
from entrypoints.composition_root import build_app

_JOB_NAME = "sync-knowledge-base"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync knowledge sources to the database")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    args = parser.parse_args(argv)

    app = build_app()
    use_case = app.sync_knowledge_base()

    with _maybe_cron_lock(app.backend_name) as acquired:
        if acquired is False:
            print(f"[{_JOB_NAME}] previous run still in flight; skipping.", file=sys.stderr)
            return 0
        with cron_audit(app.audit_log_repository, _JOB_NAME) as audit:
            result = use_case.run()
            audit["total_documents"] = result.total_documents
            audit["total_chunks"] = result.total_chunks
            audit["sources_synced"] = len(result.per_source)

    for source_result in result.per_source:
        print(
            f"[{source_result.source.value:<14}] "
            f"documents={source_result.documents_synced:<3} "
            f"chunks={source_result.chunks_written}"
        )
    print(
        f"[total          ] documents={result.total_documents} chunks={result.total_chunks} "
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
