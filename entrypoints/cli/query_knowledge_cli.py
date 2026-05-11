"""Smoke-test entrypoint: query the knowledge base from the command line.

This is NOT a cron job. It exists for an operator (or a test) to type a
free-text question and see the top-K knowledge chunks the retriever would
hand to the drafter. Useful for verifying retrieval quality after every
SyncKnowledgeBase run.

Usage:

    .venv/bin/python -m entrypoints.cli.query_knowledge_cli \\
        "video player crash on iPhone 14 after the latest update"

    .venv/bin/python -m entrypoints.cli.query_knowledge_cli \\
        --top-k 5 \\
        "TOI Plus paywall not lifting after payment"
"""

from __future__ import annotations

import argparse
import sys

from entrypoints.composition_root import build_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query the knowledge base")
    parser.add_argument("query", help="Free-text query (e.g. 'video crash on iPhone')")
    parser.add_argument("--top-k", type=int, default=8, help="How many chunks to return")
    args = parser.parse_args(argv)

    app = build_app()
    retriever = app.knowledge_retriever()
    results = list(retriever.retrieve(args.query, top_k=args.top_k))

    if not results:
        print("(no matches)", file=sys.stderr)
        return 1

    print(f"\nTop {len(results)} chunks for: {args.query!r}\n")
    for index, chunk in enumerate(results, start=1):
        snippet = chunk.content.replace("\n", " ").strip()
        if len(snippet) > 220:
            snippet = snippet[:217] + "..."
        print(f"{index}. {chunk.source_title}")
        print(f"   score={chunk.score:.4f}  url={chunk.source_url or '(none)'}")
        print(f"   {snippet}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
