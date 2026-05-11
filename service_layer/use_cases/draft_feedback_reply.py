"""DraftFeedbackReply — for each unanswered, follow-up-worthy feedback, write a draft.

Pipeline per feedback:

  1. Skip if the feedback has no classification, or the classification
     says `requires_followup=false`, or a draft already exists.
  2. Retrieve top-K knowledge chunks via the KnowledgeRetrieverPort.
  3. Render the prompt template (`prompts/draft_reply.md`) with the
     feedback + classification + numbered retrieved chunks.
  4. Call the language model.
  5. Parse the JSON response. Extract body, language, cited indices.
  6. Build a `Citation` per cited chunk (with source_url and snippet
     so support staff can verify each claim).
  7. Persist the draft via DraftReplyRepositoryPort.
  8. Deliver via ReplyDeliveryPort (Gmail draft writer for emails,
     filesystem writer for store reviews — chosen by the composition
     root based on channel).

The drafter is the "second half" of TOI's brief: ingestion + classify
+ cluster + spike feeds the alerting story; drafter feeds the reply
story. After this use case the support team's inbox has ready-to-edit
drafts grounded in real internal facts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain.classification import Classification
from domain.draft_reply import Citation, DraftReply
from domain.exceptions import DraftGenerationError
from domain.feedback import Feedback
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.draft_reply_repository_port import DraftReplyRepositoryPort
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort
from service_layer.ports.knowledge_retriever_port import (
    KnowledgeRetrieverPort,
    RetrievedChunk,
)
from service_layer.ports.language_model_port import LanguageModelPort
from service_layer.ports.reply_delivery_port import ReplyDeliveryPort

_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "draft_reply.md"
)


@dataclass(frozen=True)
class DraftFeedbackReplyResult:
    drafted: int
    skipped_no_classification: int
    skipped_no_followup: int
    skipped_already_drafted: int
    failed: int


class DraftFeedbackReply:
    def __init__(
        self,
        feedback_repository: FeedbackRepositoryPort,
        classification_repository: ClassificationRepositoryPort,
        draft_reply_repository: DraftReplyRepositoryPort,
        knowledge_retriever: KnowledgeRetrieverPort,
        language_model: LanguageModelPort,
        reply_delivery: ReplyDeliveryPort,
        app_name_lookup: dict[str, str] | None = None,
        retrieval_top_k: int = 8,
        prompt_template: str | None = None,
    ) -> None:
        self._feedback_repository = feedback_repository
        self._classification_repository = classification_repository
        self._draft_reply_repository = draft_reply_repository
        self._knowledge_retriever = knowledge_retriever
        self._language_model = language_model
        self._reply_delivery = reply_delivery
        self._app_name_lookup = app_name_lookup or {}
        self._retrieval_top_k = retrieval_top_k
        self._prompt_template = prompt_template or _PROMPT_PATH.read_text(encoding="utf-8")

    def run(self, app_slug: str | None = None, limit: int = 50) -> DraftFeedbackReplyResult:
        drafted = 0
        no_classification = 0
        no_followup = 0
        already_drafted = 0
        failed = 0

        candidates = list(self._feedback_repository.list_by_filters(app_slug=app_slug))[:limit]
        for feedback in candidates:
            classification = self._classification_repository.get(feedback.id)
            if classification is None:
                no_classification += 1
                continue
            if not classification.requires_followup:
                no_followup += 1
                continue
            if self._draft_reply_repository.has_draft_for(feedback.id):
                already_drafted += 1
                continue

            try:
                draft = self._draft_one(feedback, classification)
                self._draft_reply_repository.add(draft)
                self._reply_delivery.deliver(feedback, draft)
                drafted += 1
            except DraftGenerationError:
                failed += 1

        return DraftFeedbackReplyResult(
            drafted=drafted,
            skipped_no_classification=no_classification,
            skipped_no_followup=no_followup,
            skipped_already_drafted=already_drafted,
            failed=failed,
        )

    # ─── internals ────────────────────────────────────────────────────────

    def _draft_one(
        self, feedback: Feedback, classification: Classification
    ) -> DraftReply:
        retrieved_chunks = list(
            self._knowledge_retriever.retrieve(
                feedback.raw_text, top_k=self._retrieval_top_k
            )
        )

        prompt = self._build_prompt(feedback, classification, retrieved_chunks)
        raw_response = self._language_model.complete(prompt)
        parsed = _parse_response(raw_response)

        body = parsed.get("body", "").strip()
        if not body:
            raise DraftGenerationError("Language model returned empty body.")
        language_code = parsed.get("language_code") or feedback.language_code or "en"
        cited_indices = [int(i) for i in parsed.get("cited_chunk_indices", [])]

        citations = _build_citations(retrieved_chunks, cited_indices)
        return DraftReply(
            feedback_id=feedback.id,
            language_code=language_code,
            body=body,
            citations=citations,
            metadata={
                "language_model_used": self._language_model.name,
                "retrieval_top_k": self._retrieval_top_k,
            },
        )

    def _build_prompt(
        self,
        feedback: Feedback,
        classification: Classification,
        chunks: list[RetrievedChunk],
    ) -> str:
        retrieved_block = _format_chunks(chunks)
        return self._prompt_template.format(
            app_slug=feedback.app_slug,
            app_name=self._app_name_lookup.get(feedback.app_slug, feedback.app_slug),
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
            retrieved_chunks_block=retrieved_block,
        )


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no internal facts found — write a careful acknowledgement reply only)"
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        lines.append(f"[{index}] {chunk.source_title}")
        if chunk.source_url:
            lines.append(f"    URL: {chunk.source_url}")
        # Keep snippets short in the prompt; the full chunk is in the
        # database for the dashboard to show on click-through.
        snippet = chunk.content.replace("\n", " ").strip()
        if len(snippet) > 600:
            snippet = snippet[:597] + "..."
        lines.append(f"    {snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def _parse_response(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DraftGenerationError(
                f"Language model returned non-JSON: {raw!r}"
            ) from exc
    raise DraftGenerationError(f"Unexpected response type: {type(raw).__name__}")


def _build_citations(
    chunks: list[RetrievedChunk], cited_indices: list[int]
) -> list[Citation]:
    citations: list[Citation] = []
    for index in cited_indices:
        if index < 1 or index > len(chunks):
            continue  # ignore out-of-range citations the model invented
        chunk = chunks[index - 1]
        snippet = chunk.content.replace("\n", " ").strip()
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."
        citations.append(
            Citation(
                knowledge_chunk_id=chunk.knowledge_chunk_id,
                source_url=chunk.source_url,
                source_title=chunk.source_title,
                snippet=snippet,
            )
        )
    return citations
