"""Tests for the JSON-extraction helper used by every real LLM adapter."""

import pytest

from adapters.language_models._response_parsing import (
    LanguageModelResponseError,
    parse_json_from_response,
)


def test_parses_pure_json():
    assert parse_json_from_response('{"category": "bug"}') == {"category": "bug"}


def test_strips_markdown_fence_with_language_hint():
    raw = '```json\n{"category": "bug", "severity": "high"}\n```'
    assert parse_json_from_response(raw) == {"category": "bug", "severity": "high"}


def test_strips_markdown_fence_without_language_hint():
    raw = '```\n{"category": "bug"}\n```'
    assert parse_json_from_response(raw) == {"category": "bug"}


def test_handles_prose_around_json():
    raw = 'Sure! Here is the classification:\n\n{"category": "bug"}\n\nLet me know if you need more.'
    assert parse_json_from_response(raw) == {"category": "bug"}


def test_handles_nested_objects():
    raw = '```json\n{"category": "bug", "entities": {"device": "Pixel 7"}}\n```'
    parsed = parse_json_from_response(raw)
    assert parsed["entities"] == {"device": "Pixel 7"}


def test_raises_on_empty_response():
    with pytest.raises(LanguageModelResponseError):
        parse_json_from_response("")


def test_raises_when_no_json_anywhere():
    with pytest.raises(LanguageModelResponseError):
        parse_json_from_response("I'm sorry, I can't help with that.")
