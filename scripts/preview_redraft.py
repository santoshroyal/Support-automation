"""Preview a redraft for one feedback against the current prompt template.

Read-only. Does NOT delete or insert anything. The point of this script is
to demonstrate what the drafter would produce with the latest
`prompts/draft_reply.md` for a specific feedback, before we commit to
permanently regenerating its draft.

Usage:
    .venv/bin/python -m scripts.preview_redraft <feedback_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from entrypoints.composition_root import build_app
from service_layer.use_cases.draft_feedback_reply import (
    DraftFeedbackReply,
    _PROMPT_PATH,
    _build_citations,
    _format_chunks,
    _parse_response,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feedback_id", help="UUID of the feedback to preview")
    args = parser.parse_args(argv)

    feedback_id = UUID(args.feedback_id)
    app = build_app()

    feedback = app.feedback_repository.get(feedback_id)
    if feedback is None:
        print(f"No feedback found for id {feedback_id}", file=sys.stderr)
        return 1

    classification = app.classification_repository.get(feedback_id)
    if classification is None:
        print("No classification — cannot draft.", file=sys.stderr)
        return 1

    retriever = app.knowledge_retriever()
    chunks = list(retriever.retrieve(feedback.raw_text, top_k=8))

    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    app_name = next(
        (a.name for a in app.app_registry if a.slug == feedback.app_slug),
        feedback.app_slug,
    )
    prompt = prompt_template.format(
        app_slug=feedback.app_slug,
        app_name=app_name,
        channel=feedback.channel.value,
        platform=feedback.platform.value,
        language_hint=feedback.language_code or "unknown",
        app_version=feedback.app_version or "unknown",
        device=feedback.device_info or "unknown",
        feedback_text=feedback.raw_text,
        category=classification.category.value,
        sub_category=classification.sub_category or "(none)",
        severity=classification.severity.value,
        sentiment=classification.sentiment.value,
        retrieved_chunks_block=_format_chunks(chunks),
    )

    print("=" * 72)
    print(f"FEEDBACK  {feedback_id}")
    print(f"App       {feedback.app_slug}  Channel  {feedback.channel.value}")
    print(f"Text      {feedback.raw_text!r}")
    print("=" * 72)

    raw = app.language_model.complete(prompt)
    parsed = _parse_response(raw)

    body = parsed.get("body", "").strip()
    language_code = parsed.get("language_code") or feedback.language_code or "en"
    cited_indices = [int(i) for i in parsed.get("cited_chunk_indices", [])]

    print()
    print(f"LANGUAGE  {language_code}")
    print(f"MODEL     {app.language_model.name}")
    print()
    print("NEW DRAFT BODY (would be sent to user):")
    print("-" * 72)
    print(body)
    print("-" * 72)
    print()
    print("CITATIONS (visible to support staff only, not the user):")
    citations = _build_citations(chunks, cited_indices)
    for index, citation in enumerate(citations, start=1):
        print(f"  [{index}] {citation.source_title}  {citation.source_url or ''}")
    if not citations:
        print("  (none)")
    print()
    print("(Nothing was persisted. Re-run the drafter CLI to write to disk + DB.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
