"""Helpers shared by the real language-model adapters.

LLMs frequently wrap structured output in markdown fences (```json ... ```)
or pad it with prose. Each adapter still has to extract a JSON object from
the model's reply. This module centralises that messy heuristic so the
adapters stay tiny.
"""

from __future__ import annotations

import json
import re
from typing import Any

from domain.exceptions import DomainError


class LanguageModelResponseError(DomainError):
    """The language model produced output we couldn't turn into a JSON object."""


_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_from_response(raw_text: str) -> Any:
    """Pull a JSON object out of a model's free-text reply.

    Strategy:
      1. If the whole response is valid JSON, use it.
      2. Otherwise look for the first ``` ... ``` block (with or without
         the `json` language hint) and parse its contents.
      3. Otherwise look for the first {...} or [...] span and parse that.

    Raises LanguageModelResponseError if none of the strategies yield JSON.
    """
    text = raw_text.strip()
    if not text:
        raise LanguageModelResponseError("Language model returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = _FENCE_PATTERN.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    span = _first_balanced_span(text)
    if span is not None:
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            pass

    raise LanguageModelResponseError(
        f"Could not parse JSON from language model response: {raw_text!r}"
    )


def _first_balanced_span(text: str) -> str | None:
    """Return the first balanced { ... } or [ ... ] substring, if any."""
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return None
