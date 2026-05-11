"""FastAPI `Depends()` factories.

Each function in here pulls a port from the composition root and
returns it. Routes declare these as parameters and FastAPI injects them
per request:

    from fastapi import Depends
    from entrypoints.web_api.dependencies import feedback_repository

    @router.get("/api/feedback")
    def list_feedback(repo = Depends(feedback_repository)):
        return list(repo.list_by_filters())

Why a thin wrapper module: keeps the composition root the single source
of truth for wiring while letting FastAPI's dependency-injection
mechanism work naturally. Tests can override these `Depends` with
`app.dependency_overrides[feedback_repository] = lambda: fake_repo`.
"""

from __future__ import annotations

from adapters.settings.app_registry import AppRegistry
from entrypoints.composition_root import WiredApp, build_app
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.draft_reply_repository_port import DraftReplyRepositoryPort
from service_layer.ports.feedback_cluster_repository_port import (
    FeedbackClusterRepositoryPort,
)
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort
from service_layer.ports.knowledge_repository_port import KnowledgeRepositoryPort
from service_layer.ports.spike_event_repository_port import SpikeEventRepositoryPort


def wired_app() -> WiredApp:
    return build_app()


def feedback_repository() -> FeedbackRepositoryPort:
    return build_app().feedback_repository


def classification_repository() -> ClassificationRepositoryPort:
    return build_app().classification_repository


def cluster_repository() -> FeedbackClusterRepositoryPort:
    return build_app().cluster_repository


def spike_event_repository() -> SpikeEventRepositoryPort:
    return build_app().spike_event_repository


def knowledge_repository() -> KnowledgeRepositoryPort:
    return build_app().knowledge_repository


def draft_reply_repository() -> DraftReplyRepositoryPort:
    return build_app().draft_reply_repository


def app_registry() -> AppRegistry:
    return build_app().app_registry
