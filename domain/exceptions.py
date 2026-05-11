"""Domain-level exceptions.

Adapters and the service layer raise these when domain invariants are violated.
The web API maps them to HTTP status codes in `entrypoints/web_api/error_handlers.py`.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for all domain errors."""


class FeedbackAlreadyIngested(DomainError):
    """A feedback with the same (channel, external_id) already exists."""


class UnknownLanguageModelError(DomainError):
    """The requested language model adapter is not configured or not healthy."""


class KnowledgeRetrievalError(DomainError):
    """RAG retrieval failed (e.g. embedding model unavailable)."""


class DraftGenerationError(DomainError):
    """The drafter could not produce a draft for the given feedback."""


class SourceUnavailable(DomainError):
    """An external source (Gmail, JIRA, etc.) is currently unavailable."""
