"""Shared helper that wraps a cron run with audit-log entries.

Each cron entry-point uses `cron_audit` as a context manager:

    with cron_audit(app.audit_log_repository, _JOB_NAME) as details:
        result = use_case.run(...)
        details["drafted"] = result.drafted
        details["skipped"] = result.skipped_already_drafted

The helper writes a `<actor>.started` row on entry, a `<actor>.finished`
row (with whatever the caller put in `details`) on clean exit, and a
`<actor>.failed` row with the exception message on error. The exception
re-raises — audit-logging never swallows failures.

Lives in `entrypoints/cli/` rather than `service_layer/` because it
deals with lifecycle boundaries of CLI execution; use cases stay pure.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from domain.audit_log import AuditLogEntry
from service_layer.ports.audit_log_repository_port import AuditLogRepositoryPort


@contextmanager
def cron_audit(
    audit_repo: AuditLogRepositoryPort,
    actor: str,
) -> Iterator[dict]:
    audit_repo.add(AuditLogEntry(actor=actor, action=f"{actor}.started"))
    details: dict = {}
    try:
        yield details
    except Exception as exc:
        details["error"] = repr(exc)
        audit_repo.add(
            AuditLogEntry(actor=actor, action=f"{actor}.failed", details=details)
        )
        raise
    audit_repo.add(
        AuditLogEntry(actor=actor, action=f"{actor}.finished", details=details)
    )
