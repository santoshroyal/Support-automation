"""Loads the shipped apps.yaml and confirms the registry is wired correctly."""

from pathlib import Path

from adapters.settings.app_registry import load_app_registry

_APPS_YAML = (
    Path(__file__).resolve().parents[3] / "config_files" / "apps.yaml"
)


def test_loads_three_apps_from_shipped_yaml():
    registry = load_app_registry(_APPS_YAML)

    slugs = registry.slugs()

    assert "toi" in slugs
    assert "et" in slugs
    assert "nbt" in slugs


def test_by_slug_returns_correct_app():
    registry = load_app_registry(_APPS_YAML)

    toi = registry.by_slug("toi")

    assert toi is not None
    assert toi.name == "Times of India"
    assert toi.play_package_name is not None


def test_unknown_slug_returns_none():
    registry = load_app_registry(_APPS_YAML)

    assert registry.by_slug("does_not_exist") is None
