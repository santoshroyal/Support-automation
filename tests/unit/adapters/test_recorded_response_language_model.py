"""RecordedResponseLanguageModel — lookup, default fallback, directory loading."""

import json

import pytest

from adapters.language_models.recorded_response_language_model import (
    RecordedResponseLanguageModel,
    hash_prompt,
)
from domain.exceptions import UnknownLanguageModelError


def test_returns_recorded_response_for_matching_prompt():
    prompt = "classify this please"
    recordings = {hash_prompt(prompt): {"category": "praise", "severity": "low"}}
    model = RecordedResponseLanguageModel(recordings=recordings)

    response = model.complete(prompt)

    assert response == {"category": "praise", "severity": "low"}


def test_returns_default_response_when_prompt_not_recorded():
    default = {"category": "other"}
    model = RecordedResponseLanguageModel(recordings={}, default_response=default)

    assert model.complete("anything") == default


def test_raises_when_no_recording_and_no_default():
    model = RecordedResponseLanguageModel(recordings={})

    with pytest.raises(UnknownLanguageModelError):
        model.complete("anything")


def test_hash_is_stable_across_trailing_whitespace():
    assert hash_prompt("hello") == hash_prompt("hello\n")
    assert hash_prompt("hello") == hash_prompt("hello   ")
    assert hash_prompt("hello") != hash_prompt("hello world")


def test_loads_recordings_from_directory(tmp_path):
    prompt = "classify ABC"
    payload = {
        "label": "test",
        "prompt_signature": hash_prompt(prompt),
        "response": {"category": "bug"},
    }
    (tmp_path / "abc.json").write_text(json.dumps(payload))

    model = RecordedResponseLanguageModel.from_directory(tmp_path)

    assert model.complete(prompt) == {"category": "bug"}


def test_directory_loader_handles_missing_dir(tmp_path):
    model = RecordedResponseLanguageModel.from_directory(
        tmp_path / "nope", default_response={"x": 1}
    )

    assert model.complete("anything") == {"x": 1}
