"""Error-handler tests — confirm the catch-all hides stack traces."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from entrypoints.web_api.error_handlers import register_error_handlers


def test_unhandled_exception_returns_internal_with_trace_id():
    """A route that raises an unexpected error returns 500 with a
    trace_id — never the underlying exception message or stack.

    Builds a minimal FastAPI app rather than going through `create_app()`
    so the test isolates the error-handler behaviour from other route
    registrations (especially the SPA static-mount catch-all).
    """
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/_boom")
    def _boom() -> dict:
        raise RuntimeError("this is a sensitive internal detail")

    # raise_server_exceptions=False makes the TestClient behave like a
    # real HTTP client (returning the response) instead of re-raising.
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/_boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal"
    assert "trace_id" in body
    assert len(body["trace_id"]) >= 16  # uuid4 hex is 32 chars; sanity check
    # The crucial part: nothing about the exception leaks to the client.
    assert "sensitive internal detail" not in response.text
    assert "RuntimeError" not in response.text


def test_trace_id_differs_between_requests():
    """Each 500 gets its own trace_id so they can be cross-referenced
    with the corresponding log lines individually."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/_boom")
    def _boom() -> dict:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)

    first = client.get("/_boom").json()["trace_id"]
    second = client.get("/_boom").json()["trace_id"]
    assert first != second
