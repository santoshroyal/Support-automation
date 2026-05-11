"""LanguageModelRouter — health-checked fallback chain."""

import pytest

from adapters.language_models.language_model_router import LanguageModelRouter
from domain.exceptions import UnknownLanguageModelError


class _FakeModel:
    def __init__(self, name, healthy=True, raises=None, returns=None):
        self.name = name
        self._healthy = healthy
        self._raises = raises
        self._returns = returns
        self.call_count = 0

    def is_healthy(self):
        return self._healthy

    def complete(self, prompt, schema=None):
        self.call_count += 1
        if self._raises is not None:
            raise self._raises
        return self._returns


def test_routes_to_first_healthy_candidate():
    primary = _FakeModel("primary", returns="from_primary")
    fallback = _FakeModel("fallback", returns="from_fallback")

    router = LanguageModelRouter([primary, fallback])

    assert router.complete("hi") == "from_primary"
    assert primary.call_count == 1
    assert fallback.call_count == 0


def test_falls_through_unhealthy_to_next():
    unhealthy = _FakeModel("unhealthy", healthy=False)
    healthy = _FakeModel("healthy", returns="ok")

    router = LanguageModelRouter([unhealthy, healthy])

    assert router.complete("hi") == "ok"
    assert unhealthy.call_count == 0
    assert healthy.call_count == 1


def test_fallback_when_primary_raises():
    primary = _FakeModel("primary", raises=RuntimeError("boom"))
    fallback = _FakeModel("fallback", returns="rescued")

    assert LanguageModelRouter([primary, fallback]).complete("hi") == "rescued"


def test_active_name_reports_first_healthy():
    unhealthy = _FakeModel("a", healthy=False)
    healthy = _FakeModel("b", returns="ok")
    assert LanguageModelRouter([unhealthy, healthy]).active_name == "b"


def test_raises_when_no_candidate_is_healthy():
    one = _FakeModel("a", healthy=False)
    two = _FakeModel("b", healthy=False)

    with pytest.raises(UnknownLanguageModelError):
        LanguageModelRouter([one, two]).complete("hi")


def test_raises_when_all_healthy_candidates_fail():
    one = _FakeModel("a", raises=RuntimeError("fail"))
    two = _FakeModel("b", raises=RuntimeError("fail too"))

    with pytest.raises(UnknownLanguageModelError):
        LanguageModelRouter([one, two]).complete("hi")


def test_constructor_rejects_empty_chain():
    with pytest.raises(ValueError):
        LanguageModelRouter([])
