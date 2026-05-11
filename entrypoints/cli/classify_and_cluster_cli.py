"""Cron entrypoint: classify every unclassified feedback, then cluster every unclustered one.

Two narrow steps run back-to-back so a single cron tick advances both signals:

  1. ClassifyFeedback — for each feedback without a classification, ask the
     language model and persist the structured judgment.
  2. ClusterFeedback — for each feedback without a cluster membership, embed
     the text and join (or create) the closest cluster.

When running against Postgres, the work is wrapped in a `cron_lock` so a
slow predecessor (e.g. one stuck in an LLM call) doesn't get trampled by
the next scheduled tick.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager, nullcontext
from typing import Iterator

from entrypoints.composition_root import build_app

_JOB_NAME = "classify-and-cluster"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify and cluster every feedback row missing those signals"
    )
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    parser.add_argument("--app-slug", default=None, help="Limit to a single app slug")
    parser.add_argument("--limit", type=int, default=200, help="Max rows per pass")
    parser.add_argument(
        "--skip-classify", action="store_true", help="Skip the classification step"
    )
    parser.add_argument(
        "--skip-cluster", action="store_true", help="Skip the clustering step"
    )
    args = parser.parse_args(argv)

    app = build_app()

    with _maybe_cron_lock(app.backend_name) as acquired:
        if acquired is False:
            print(f"[{_JOB_NAME}] previous run still in flight; skipping.", file=sys.stderr)
            return 0

        if not args.skip_classify:
            classify_result = app.classify_feedback().run(
                app_slug=args.app_slug, limit=args.limit
            )
            print(
                f"[classify] classified={classify_result.classified} "
                f"already_classified={classify_result.skipped_already_classified} "
                f"failed={classify_result.failed} "
                f"(model={app.language_model.name}, backend={app.backend_name})"
            )

        if not args.skip_cluster:
            cluster_result = app.cluster_feedback().run(
                app_slug=args.app_slug, limit=args.limit
            )
            print(
                f"[cluster ] clustered={cluster_result.clustered} "
                f"new_clusters={cluster_result.new_clusters} "
                f"already_clustered={cluster_result.skipped_already_clustered}"
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
