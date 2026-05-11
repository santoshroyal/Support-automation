"""GET /api/health — backend status."""

from fastapi.testclient import TestClient

from entrypoints.composition_root import reset_app_for_tests
from entrypoints.web_api.main import create_app


def test_health_returns_status_and_per_check_detail():
    reset_app_for_tests()
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "degraded"}
    assert payload["backend"] in {"postgres", "in_memory"}
    check_names = {check["name"] for check in payload["checks"]}
    assert {"database", "language_model", "embedding_model"} <= check_names
