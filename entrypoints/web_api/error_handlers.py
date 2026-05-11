"""Map domain exceptions to HTTP status codes.

Routes never construct HTTPException themselves. Instead they let
domain exceptions bubble; this module turns each kind into the right
HTTP response. Keeping the mapping in one place means a route can be
written once and behave consistently no matter which port it called.
"""

from __future__ import annotations

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
