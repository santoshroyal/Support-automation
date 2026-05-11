"""GET /api/apps — configured app list."""

from fastapi.testclient import TestClient

from entrypoints.composition_root import reset_app_for_tests
from entrypoints.web_api.main import create_app


def test_apps_endpoint_returns_three_configured_apps():
    reset_app_for_tests()
    client = TestClient(create_app())

    response = client.get("/api/apps")

    assert response.status_code == 200
    payload = response.json()
    slugs = {entry["slug"] for entry in payload}
    assert {"toi", "et", "nbt"} <= slugs


def test_app_response_carries_play_package_and_apple_bundle():
    reset_app_for_tests()
    client = TestClient(create_app())

    response = client.get("/api/apps")
    toi = next(entry for entry in response.json() if entry["slug"] == "toi")

    assert toi["name"] == "Times of India"
    assert toi["play_package_name"]
    assert toi["apple_bundle_id"]
