"""Cron entrypoint: draft a reply for every feedback that needs one.

Typically scheduled every 15 minutes. Skips feedbacks that don't have
a classification yet, feedbacks the classifier marked as not requiring
follow-up (pure praise, vague content), and feedbacks that already have
a draft.

When running against Postgres the work runs inside a `cron_lock`. The
language-model call (Claude Code via subprocess) is the slow step —
expect ~5-10 seconds per draft. For 15 fixtures that's ~2 minutes.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager, nullcontext
from typing import Iterator

from entrypoints.composition_root import build_app

_JOB_NAME = "draft-replies"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draft replies for unanswered feedback")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    parser.add_argument("--app-slug", default=None, help="Limit to one app slug")
    parser.add_argument("--limit", type=int, default=50, help="Max drafts per pass")
    args = parser.parse_args(argv)

    app = build_app()
    use_case = app.draft_feedback_reply()

    with _maybe_cron_lock(app.backend_name) as acquired:
        if acquired is False:
            print(f"[{_JOB_NAME}] previous run still in flight; skipping.", file=sys.stderr)
            return 0
        result = use_case.run(app_slug=args.app_slug, limit=args.limit)

    print(
        f"[draft] drafted={result.drafted} "
        f"no_classification={result.skipped_no_classification} "
        f"no_followup={result.skipped_no_followup} "
        f"already_drafted={result.skipped_already_drafted} "
        f"failed={result.failed} "
        f"(model={app.language_model.name}, delivery={app.reply_delivery.name}, "
        f"backend={app.backend_name})"
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
