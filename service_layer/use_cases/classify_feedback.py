"""ClassifyFeedback — for each unclassified Feedback, ask the language model
for a structured judgment and persist it.

The use case is deliberately small: it depends only on the repository ports
and the language-model port. Prompt construction is delegated to a private
helper so the prompt template is the single source of truth (and so the
recorded-response adapter can hash the same string the real adapters
produce).

The language-model response is expected to be a JSON object matching the
schema documented in `prompts/classify_feedback.md`. We validate before
constructing the domain `Classification` so a bad response surfaces as a
crisp error rather than a downstream type confusion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain.classification import Classification, FeedbackCategory, Sentiment, Severity
from domain.exceptions import DomainError
from domain.feedback import Feedback
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort
from service_layer.ports.language_model_port import LanguageModelPort

_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "classify_feedback.md"
)


@dataclass(frozen=True)
class ClassifyFeedbackResult:
    classified: int
    skipped_already_classified: int
    failed: int


class ClassificationResponseError(DomainError):
    """The language model returned something we couldn't turn into a Classification."""


class ClassifyFeedback:
    def __init__(
        self,
        feedback_repository: FeedbackRepositoryPort,
        classification_repository: ClassificationRepositoryPort,
        language_model: LanguageModelPort,
        app_name_lookup: dict[str, str] | None = None,
        prompt_template: str | None = None,
    ) -> None:
        self._feedback_repository = feedback_repository
        self._classification_repository = classification_repository
        self._language_model = language_model
        self._app_name_lookup = app_name_lookup or {}
        self._prompt_template = prompt_template or _PROMPT_PATH.read_text(encoding="utf-8")

    def run(self, app_slug: str | None = None, limit: int = 100) -> ClassifyFeedbackResult:
        classified = 0
        skipped = 0
        failed = 0

        for feedback in self._feedback_repository.list_unclassified(
            app_slug=app_slug, limit=limit
        ):
            if self._classification_repository.has_classification_for(feedback.id):
                skipped += 1
                continue
            try:
                classification = self._classify_one(feedback)
                self._classification_repository.add(classification)
                classified += 1
            except (ClassificationResponseError, ValueError):
                failed += 1

        return ClassifyFeedbackResult(
            classified=classified,
            skipped_already_classified=skipped,
            failed=failed,
        )

    def build_prompt(self, feedback: Feedback) -> str:
        """Public so the recorded-response adapter (and tests) can hash the same string."""
        return self._prompt_template.format(
            app_slug=feedback.app_slug,
            app_name=self._app_name_lookup.get(feedback.app_slug, feedback.app_slug),
            channel=feedback.channel.value,
            platform=feedback.platform.value,
            language_hint=feedback.language_code or "unknown",
            app_version=feedback.app_version or "unknown",
            device=feedback.device_info or "unknown",
            feedback_text=feedback.raw_text,
        )

    def _classify_one(self, feedback: Feedback) -> Classification:
        prompt = self.build_prompt(feedback)
        raw_response = self._language_model.complete(prompt)
        return _to_classification(raw_response, feedback, self._language_model.name)


def _to_classification(
    raw_response: Any, feedback: Feedback, model_name: str
) -> Classification:
    payload = _normalise_response(raw_response)
    try:
        category = FeedbackCategory(payload["category"])
        severity = Severity(payload["severity"])
        sentiment = Sentiment(payload["sentiment"])
    except (KeyError, ValueError) as exc:
        raise ClassificationResponseError(
            f"Language model response missing or invalid required fields: {payload!r}"
        ) from exc

    return Classification(
        feedback_id=feedback.id,
        category=category,
        severity=severity,
        sentiment=sentiment,
        sub_category=payload.get("sub_category"),
        entities=dict(payload.get("entities") or {}),
        requires_followup=bool(payload.get("requires_followup", True)),
        language_model_used=model_name,
    )


def _normalise_response(raw: Any) -> dict[str, Any]:
    """Accept either a dict (preferred) or a JSON string."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ClassificationResponseError(
                f"Language model returned non-JSON string: {raw!r}"
            ) from exc
    raise ClassificationResponseError(f"Unexpected response type: {type(raw).__name__}")
