"""Map domain exceptions to HTTP status codes.

Routes never construct HTTPException themselves. Instead they let
domain exceptions bubble; this module turns each kind into the right
HTTP response. Keeping the mapping in one place means a route can be
written once and behave consistently no matter which port it called.

The generic `Exception` handler at the bottom is the safety net for
**unknown** errors: it returns a small JSON body with a `trace_id` and
logs the full exception (including the trace_id) so support staff can
correlate a 500 a user saw with the underlying stack trace, without
leaking the trace itself in the HTTP response.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from domain.exceptions import (
    DomainError,
    DraftGenerationError,
    FeedbackAlreadyIngested,
    KnowledgeRetrievalError,
    SourceUnavailable,
    UnknownLanguageModelError,
)

_logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FeedbackAlreadyIngested)
    async def _already_ingested(request: Request, exc: FeedbackAlreadyIngested):  # noqa: ARG001
        return JSONResponse(
            status_code=409,
            content={"error": "feedback_already_ingested", "detail": str(exc)},
        )

    @app.exception_handler(SourceUnavailable)
    async def _source_unavailable(request: Request, exc: SourceUnavailable):  # noqa: ARG001
        return JSONResponse(
            status_code=503,
            content={"error": "source_unavailable", "detail": str(exc)},
        )

    @app.exception_handler(UnknownLanguageModelError)
    async def _language_model_unhealthy(request, exc):  # noqa: ARG001
        return JSONResponse(
            status_code=503,
            content={"error": "language_model_unhealthy", "detail": str(exc)},
        )

    @app.exception_handler(KnowledgeRetrievalError)
    async def _retrieval_error(request, exc):  # noqa: ARG001
        return JSONResponse(
            status_code=500,
            content={"error": "knowledge_retrieval_failed", "detail": str(exc)},
        )

    @app.exception_handler(DraftGenerationError)
    async def _draft_error(request, exc):  # noqa: ARG001
        return JSONResponse(
            status_code=500,
            content={"error": "draft_generation_failed", "detail": str(exc)},
        )

    @app.exception_handler(DomainError)
    async def _domain_error(request, exc):  # noqa: ARG001
        # Catch-all for any other domain exception so the response shape
        # stays consistent instead of leaking a Python stack trace.
        return JSONResponse(
            status_code=400,
            content={"error": "domain_error", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        """Final safety net for anything we didn't anticipate.

        Returns a small response with a `trace_id` and writes the full
        exception (with the same trace_id) to the JSON log. Support
        staff use the trace_id to find the matching log entry without
        the user ever seeing the Python stack trace.
        """
        trace_id = uuid.uuid4().hex
        _logger.exception(
            "unhandled exception serving %s %s",
            request.method,
            request.url.path,
            extra={"trace_id": trace_id, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={"error": "internal", "trace_id": trace_id},
        )
