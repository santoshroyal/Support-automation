"""Record real language-model responses for the classification pipeline.

What this does:
  - Loads every Feedback fixture by running the local feedback sources.
  - Builds the classification prompt for each one.
  - Asks the configured LanguageModelRouter (skipping the Recorded
    candidate, which doesn't add value to a recording run) to classify it.
  - Saves the (prompt_hash, response) pair as a JSON file under
    `data_fixtures/language_model_responses/`.

Subsequent runs of the classify CLI use these recordings via the
RecordedResponseLanguageModel — making CI deterministic and removing the
need for a real LLM to be available on every machine.

Run (after installing Claude Code or another model in your config):

    .venv/bin/python scripts/record_llm_responses.py

Add `--limit N` to record only the first N fixtures, useful for a smoke test.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure top-level packages resolve when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from adapters.language_models._response_parsing import LanguageModelResponseError  # noqa: E402
from adapters.language_models.recorded_response_language_model import hash_prompt  # noqa: E402
from domain.feedback import Feedback  # noqa: E402
from entrypoints.composition_root import build_app  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record language-model responses for every fixture feedback"
    )
    parser.add_argument("--limit", type=int, default=None, help="Record only the first N feedbacks")
    parser.add_argument(
        "--app-slug", default=None, help="Limit to a single app slug (e.g. toi)"
    )
    args = parser.parse_args(argv)

    app = build_app()
    output_dir = Path(
        app.config.absolute(app.config.data_fixtures_dir / "language_model_responses")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    classify = app.classify_feedback()

    # Use the local feedback sources directly so we don't depend on the
    # database being populated. We just need each Feedback object so we
    # can build its prompt.
    feedbacks = list(_collect_fixture_feedbacks(app, args.app_slug, args.limit))
    if not feedbacks:
        print("No feedbacks found to record. Aborting.", file=sys.stderr)
        return 1

    recorded = 0
    skipped = 0
    failed = 0
    for index, feedback in enumerate(feedbacks, start=1):
        prompt = classify.build_prompt(feedback)
        signature = hash_prompt(prompt)
        target = output_dir / f"{feedback.app_slug}_{feedback.channel.value}_{feedback.external_id}.json"

        if target.exists():
            print(f"[{index}/{len(feedbacks)}] skip (already recorded): {target.name}")
            skipped += 1
            continue

        print(f"[{index}/{len(feedbacks)}] recording: {feedback.app_slug}/{feedback.channel.value}/{feedback.external_id}")
        try:
            response = app.language_model.complete(prompt)
        except LanguageModelResponseError as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed += 1
            continue

        payload = {
            "label": (
                f"{feedback.app_slug} / {feedback.channel.value} / {feedback.platform.value}"
                f" / {feedback.external_id}"
            ),
            "prompt_signature": signature,
            "response": response,
        }
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        recorded += 1

    print(
        f"\nDone. recorded={recorded} skipped={skipped} failed={failed}. "
        f"Recordings live in {output_dir}"
    )
    return 0 if failed == 0 else 1


def _collect_fixture_feedbacks(app, app_slug_filter, limit) -> list[Feedback]:
    feedbacks: list[Feedback] = []
    for source in app.feedback_sources:
        if app_slug_filter is not None and source.app_slug != app_slug_filter:
            continue
        for raw in source.fetch_new(since=None):
            feedbacks.append(Feedback.from_raw(raw))
            if limit is not None and len(feedbacks) >= limit:
                return feedbacks
    return feedbacks


if __name__ == "__main__":
    sys.exit(main())
