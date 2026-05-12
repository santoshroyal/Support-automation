"""Composition root — wires ports to concrete adapter implementations.

The single place that knows the full object graph. Use cases and the JSON API
depend only on this module's factory functions, not on any specific adapter
class.

Backend selection:
- `DATABASE_URL` set → PostgreSQL repositories.
- Otherwise → in-memory repositories. CI and local dev work without external
  services; integration tests opt in by setting the env var.

Per-app wiring: for each configured Times Internet app we instantiate one
local source per channel. Adding another app to `config_files/apps.yaml` is
enough — no code change here.

Language model: phase-1 ships the recorded-response adapter wired in by
default (no external tools required). Real adapters (Claude Code, Codex,
Ollama) arrive in the next sub-sprint behind a `LanguageModelRouter`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from adapters.feedback_sources.local_apple_app_store_feedback_source import (
    LocalAppleAppStoreFeedbackSource,
)
from adapters.feedback_sources.local_gmail_feedback_source import LocalGmailFeedbackSource
from adapters.feedback_sources.local_google_play_feedback_source import (
    LocalGooglePlayFeedbackSource,
)
from adapters.knowledge_sources.local_confluence_knowledge_source import (
    LocalConfluenceKnowledgeSource,
)
from adapters.knowledge_sources.local_google_sheets_knowledge_source import (
    LocalGoogleSheetsKnowledgeSource,
)
from adapters.knowledge_sources.local_jira_knowledge_source import (
    LocalJiraKnowledgeSource,
)
from adapters.language_models.router_builder import build_language_model_router
from adapters.persistence.classification_repository_postgres import (
    ClassificationRepositoryPostgres,
)
from adapters.persistence.feedback_cluster_repository_postgres import (
    FeedbackClusterRepositoryPostgres,
)
from adapters.persistence.feedback_repository_postgres import FeedbackRepositoryPostgres
from adapters.persistence.in_memory_classification_repository import (
    InMemoryClassificationRepository,
)
from adapters.persistence.in_memory_feedback_cluster_repository import (
    InMemoryFeedbackClusterRepository,
)
from adapters.persistence.in_memory_feedback_repository import InMemoryFeedbackRepository
from adapters.persistence.in_memory_knowledge_repository import (
    InMemoryKnowledgeRepository,
)
from adapters.persistence.knowledge_repository_postgres import (
    KnowledgeRepositoryPostgres,
)
from adapters.persistence.digest_log_repository_postgres import (
    DigestLogRepositoryPostgres,
)
from adapters.persistence.in_memory_digest_log_repository import (
    InMemoryDigestLogRepository,
)
from adapters.persistence.audit_log_repository_postgres import (
    AuditLogRepositoryPostgres,
)
from adapters.persistence.in_memory_audit_log_repository import (
    InMemoryAuditLogRepository,
)
from adapters.persistence.in_memory_spike_event_repository import (
    InMemorySpikeEventRepository,
)
from adapters.persistence.spike_event_repository_postgres import (
    SpikeEventRepositoryPostgres,
)
from adapters.notification.local_email_sender import LocalEmailSender
from adapters.persistence.draft_reply_repository_postgres import (
    DraftReplyRepositoryPostgres,
)
from adapters.persistence.in_memory_draft_reply_repository import (
    InMemoryDraftReplyRepository,
)
from adapters.reply_delivery.filesystem_draft_writer import FilesystemDraftWriter
from adapters.retrieval.hybrid_retriever import HybridKnowledgeRetriever
from adapters.retrieval.in_memory_knowledge_retriever import InMemoryKnowledgeRetriever
from adapters.settings.app_registry import AppRegistry, load_app_registry
from adapters.settings.stakeholder_registry import (
    filter_for_digest,
    load_stakeholders,
)
from config import AppConfig, get_config
from domain.app import App
from service_layer.ports.classification_repository_port import (
    ClassificationRepositoryPort,
)
from service_layer.ports.embedding_model_port import EmbeddingModelPort
from service_layer.ports.feedback_cluster_repository_port import (
    FeedbackClusterRepositoryPort,
)
from service_layer.ports.feedback_repository_port import FeedbackRepositoryPort
from service_layer.ports.feedback_source_port import FeedbackSourcePort
from service_layer.ports.knowledge_repository_port import KnowledgeRepositoryPort
from service_layer.ports.knowledge_retriever_port import KnowledgeRetrieverPort
from service_layer.ports.knowledge_source_port import KnowledgeSourcePort
from service_layer.ports.language_model_port import LanguageModelPort
from service_layer.ports.digest_log_repository_port import DigestLogRepositoryPort
from service_layer.ports.draft_reply_repository_port import DraftReplyRepositoryPort
from service_layer.ports.notification_sender_port import NotificationSenderPort
from service_layer.ports.reply_delivery_port import ReplyDeliveryPort
from service_layer.ports.audit_log_repository_port import AuditLogRepositoryPort
from service_layer.ports.spike_event_repository_port import SpikeEventRepositoryPort
from service_layer.use_cases.classify_feedback import ClassifyFeedback
from service_layer.use_cases.cluster_feedback import ClusterFeedback
from service_layer.use_cases.detect_complaint_spike import DetectComplaintSpike
from service_layer.use_cases.draft_feedback_reply import DraftFeedbackReply
from service_layer.use_cases.ingest_feedback import IngestFeedback
from service_layer.use_cases.send_stakeholder_digest import SendStakeholderDigest
from service_layer.use_cases.sync_knowledge_base import SyncKnowledgeBase


# Default response used by the recorded LLM when a particular prompt has not
# been recorded yet. Lets the pipeline run end-to-end before the response
# corpus is populated; obviously labelled so it's never confused with real output.
_DEFAULT_LANGUAGE_MODEL_RESPONSE: dict[str, Any] = {
    "category": "other",
    "sub_category": "unrecorded_default",
    "severity": "medium",
    "sentiment": "neutral",
    "entities": {},
    "requires_followup": True,
}


@dataclass
class WiredApp:
    """Object graph held for the lifetime of a CLI run or web process."""

    config: AppConfig
    app_registry: AppRegistry
    feedback_repository: FeedbackRepositoryPort
    classification_repository: ClassificationRepositoryPort
    cluster_repository: FeedbackClusterRepositoryPort
    spike_event_repository: SpikeEventRepositoryPort
    digest_log_repository: DigestLogRepositoryPort
    knowledge_repository: KnowledgeRepositoryPort
    draft_reply_repository: DraftReplyRepositoryPort
    audit_log_repository: AuditLogRepositoryPort
    feedback_sources: Sequence[FeedbackSourcePort]
    knowledge_sources: Sequence[KnowledgeSourcePort]
    language_model: LanguageModelPort
    notification_sender: NotificationSenderPort
    reply_delivery: ReplyDeliveryPort
    stakeholders: Sequence[Any]  # Stakeholder; avoids extra import in this header
    thresholds: dict[str, Any]
    backend_name: str  # "postgres" or "in_memory"
    _embedding_model: EmbeddingModelPort | None = None  # lazy
    _knowledge_retriever: KnowledgeRetrieverPort | None = None  # lazy

    @property
    def embedding_model(self) -> EmbeddingModelPort:
        """Lazy-load the embedding model (heavy: ~250 MB on first import).

        Only paid by processes that actually cluster or run RAG retrieval.
        Ingest and classify CLIs never trigger this.
        """
        if self._embedding_model is None:
            self._embedding_model = _build_embedding_model()
        return self._embedding_model

    def ingest_feedback(self) -> IngestFeedback:
        return IngestFeedback(
            sources=self.feedback_sources,
            feedback_repository=self.feedback_repository,
        )

    def classify_feedback(self) -> ClassifyFeedback:
        return ClassifyFeedback(
            feedback_repository=self.feedback_repository,
            classification_repository=self.classification_repository,
            language_model=self.language_model,
            app_name_lookup={app.slug: app.name for app in self.app_registry},
        )

    def cluster_feedback(self) -> ClusterFeedback:
        return ClusterFeedback(
            feedback_repository=self.feedback_repository,
            cluster_repository=self.cluster_repository,
            embedding_model=self.embedding_model,  # triggers lazy load
        )

    def detect_complaint_spike(self) -> DetectComplaintSpike:
        spike_thresholds = self.thresholds.get("spike_detection", {})
        return DetectComplaintSpike(
            cluster_repository=self.cluster_repository,
            spike_event_repository=self.spike_event_repository,
            min_count=int(spike_thresholds.get("min_count", 2)),
            ratio=float(spike_thresholds.get("ratio", 2.0)),
            recent_window_hours=int(spike_thresholds.get("recent_window_hours", 24)),
            baseline_window_days=int(spike_thresholds.get("baseline_window_days", 7)),
            suppression_window_hours=int(
                spike_thresholds.get("suppression_window_hours", 6)
            ),
            sample_size=int(spike_thresholds.get("sample_size", 5)),
        )

    def sync_knowledge_base(self) -> SyncKnowledgeBase:
        return SyncKnowledgeBase(
            sources=self.knowledge_sources,
            knowledge_repository=self.knowledge_repository,
            embedding_model=self.embedding_model,  # triggers lazy load
        )

    def draft_feedback_reply(self) -> DraftFeedbackReply:
        return DraftFeedbackReply(
            feedback_repository=self.feedback_repository,
            classification_repository=self.classification_repository,
            draft_reply_repository=self.draft_reply_repository,
            knowledge_retriever=self.knowledge_retriever(),
            language_model=self.language_model,
            reply_delivery=self.reply_delivery,
            app_name_lookup={app.slug: app.name for app in self.app_registry},
        )

    def knowledge_retriever(self) -> KnowledgeRetrieverPort:
        """Build the hybrid retriever (Postgres) or an empty in-memory one.

        Lazy: only instantiated when first asked. The embedding model
        loads on first use (~250 MB) so processes that don't retrieve
        (ingest, classify, spike-detect) never pay that cost.
        """
        if self._knowledge_retriever is None:
            if self.backend_name == "postgres":
                self._knowledge_retriever = HybridKnowledgeRetriever(
                    embedding_model=self.embedding_model
                )
            else:
                self._knowledge_retriever = InMemoryKnowledgeRetriever(
                    embedding_model=self.embedding_model
                )
        return self._knowledge_retriever

    def send_stakeholder_digest(self, digest_type: str) -> SendStakeholderDigest:
        digest_config = self.thresholds.get("digest", {})
        if digest_type == "hourly":
            lookback_hours = int(digest_config.get("hourly_lookback_hours", 1))
        elif digest_type == "daily":
            lookback_hours = int(digest_config.get("daily_lookback_hours", 24))
        else:
            raise ValueError(f"Unknown digest_type: {digest_type!r}")

        recipients = filter_for_digest(self.stakeholders, digest_type=digest_type)
        return SendStakeholderDigest(
            spike_event_repository=self.spike_event_repository,
            cluster_repository=self.cluster_repository,
            digest_log_repository=self.digest_log_repository,
            notification_sender=self.notification_sender,
            stakeholders=recipients,
            lookback_hours=lookback_hours,
            digest_type=digest_type,
        )


_singleton: WiredApp | None = None


def build_app() -> WiredApp:
    """Construct (or return cached) wired application."""
    global _singleton
    if _singleton is not None:
        return _singleton

    config = get_config()
    app_registry = load_app_registry(config.absolute(Path("config_files") / "apps.yaml"))

    (
        feedback_repository,
        classification_repository,
        cluster_repository,
        spike_event_repository,
        digest_log_repository,
        knowledge_repository,
        draft_reply_repository,
        audit_log_repository,
        backend_name,
    ) = _build_repositories(config)
    feedback_sources = _build_feedback_sources(config, app_registry)
    knowledge_sources = _build_knowledge_sources(config)
    language_model = _build_language_model(config)
    thresholds = _load_thresholds(config)
    stakeholders = load_stakeholders(
        config.absolute(Path("config_files") / "stakeholders.yaml")
    )
    notification_sender = _build_notification_sender(config)
    reply_delivery = _build_reply_delivery(config)

    _singleton = WiredApp(
        config=config,
        app_registry=app_registry,
        feedback_repository=feedback_repository,
        classification_repository=classification_repository,
        cluster_repository=cluster_repository,
        spike_event_repository=spike_event_repository,
        digest_log_repository=digest_log_repository,
        knowledge_repository=knowledge_repository,
        draft_reply_repository=draft_reply_repository,
        audit_log_repository=audit_log_repository,
        feedback_sources=feedback_sources,
        knowledge_sources=knowledge_sources,
        language_model=language_model,
        notification_sender=notification_sender,
        reply_delivery=reply_delivery,
        stakeholders=stakeholders,
        thresholds=thresholds,
        backend_name=backend_name,
        # _embedding_model + _knowledge_retriever load lazily on first access
    )
    return _singleton


def _build_reply_delivery(config: AppConfig) -> ReplyDeliveryPort:
    """Phase-1 default: write every draft to disk.

    The GmailDraftWriter takes over for email channels once Gmail OAuth
    credentials are in place (`secrets/gmail.json` + `gmail_token.json`).
    Until then, even email drafts land on disk under
    var/support_automation/drafts/<date>/ so support staff can copy them
    into Gmail manually.
    """
    return FilesystemDraftWriter(
        output_root=config.absolute(config.drafts_output_dir)
    )


def _build_knowledge_sources(config: AppConfig) -> list[KnowledgeSourcePort]:
    """One adapter per source. Real-mode adapters arrive in a follow-up sprint."""
    knowledge_root = Path(config.absolute(config.data_fixtures_dir / "knowledge"))
    return [
        LocalConfluenceKnowledgeSource(fixtures_dir=knowledge_root / "confluence"),
        LocalJiraKnowledgeSource(fixtures_dir=knowledge_root / "jira"),
        LocalGoogleSheetsKnowledgeSource(fixtures_dir=knowledge_root / "sheets"),
    ]


def _build_notification_sender(config: AppConfig) -> NotificationSenderPort:
    """Phase-1 default: write digests to disk (review before going live).

    The SmtpEmailSender adapter is wired in once the operator flips
    `notification.mode = "real"` in settings — that work happens in
    section H of the operations handbook.
    """
    return LocalEmailSender(output_dir=config.absolute(config.digests_output_dir))


def _load_thresholds(config: AppConfig) -> dict[str, Any]:
    import yaml

    path = config.absolute(Path("config_files") / "thresholds.yaml")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _build_repositories(
    config: AppConfig,
) -> tuple[
    FeedbackRepositoryPort,
    ClassificationRepositoryPort,
    FeedbackClusterRepositoryPort,
    SpikeEventRepositoryPort,
    DigestLogRepositoryPort,
    KnowledgeRepositoryPort,
    DraftReplyRepositoryPort,
    AuditLogRepositoryPort,
    str,
]:
    if config.use_postgres():
        return (
            FeedbackRepositoryPostgres(),
            ClassificationRepositoryPostgres(),
            FeedbackClusterRepositoryPostgres(),
            SpikeEventRepositoryPostgres(),
            DigestLogRepositoryPostgres(),
            KnowledgeRepositoryPostgres(),
            DraftReplyRepositoryPostgres(),
            AuditLogRepositoryPostgres(),
            "postgres",
        )
    return (
        InMemoryFeedbackRepository(),
        InMemoryClassificationRepository(),
        InMemoryFeedbackClusterRepository(),
        InMemorySpikeEventRepository(),
        InMemoryDigestLogRepository(),
        InMemoryKnowledgeRepository(),
        InMemoryDraftReplyRepository(),
        InMemoryAuditLogRepository(),
        "in_memory",
    )


def _build_embedding_model() -> EmbeddingModelPort:
    """Build the local multilingual sentence-transformer.

    Lazy-loaded inside the function so the heavy torch / sentence-transformers
    import cost is only paid by processes that actually run clustering or
    retrieval — the ingest CLI, for example, never embeds anything.
    """
    from adapters.embedding_models.multilingual_e5_embedding_model import (
        MultilingualE5EmbeddingModel,
    )

    return MultilingualE5EmbeddingModel()


def _build_feedback_sources(
    config: AppConfig, app_registry: AppRegistry
) -> list[FeedbackSourcePort]:
    feedback_root = Path(config.absolute(config.data_fixtures_dir / "feedback"))
    sources: list[FeedbackSourcePort] = []
    for app in app_registry:
        sources.extend(_build_sources_for_app(app, feedback_root))
    return sources


def _build_sources_for_app(app: App, feedback_root: Path) -> list[FeedbackSourcePort]:
    return [
        LocalGmailFeedbackSource(app=app, fixtures_dir=feedback_root / "gmail" / app.slug),
        LocalGooglePlayFeedbackSource(app=app, fixtures_dir=feedback_root / "play" / app.slug),
        LocalAppleAppStoreFeedbackSource(
            app=app, fixtures_dir=feedback_root / "apple" / app.slug
        ),
    ]


def _build_language_model(config: AppConfig) -> LanguageModelPort:
    """Build a LanguageModelRouter from `config_files/language_models.yaml`.

    The router probes each candidate (Claude Code, Codex, Ollama, …) for
    health and forwards each request to the first healthy one. The
    Recorded adapter is always appended as a final fallback so the cron
    pipeline cannot fail open.
    """
    config_path = config.absolute(Path("config_files") / "language_models.yaml")
    recordings_dir = Path(
        config.absolute(config.data_fixtures_dir / "language_model_responses")
    )
    return build_language_model_router(
        config_path=config_path,
        recordings_dir=recordings_dir,
        default_response=_DEFAULT_LANGUAGE_MODEL_RESPONSE,
    )


def reset_app_for_tests() -> None:
    """Drops the cached graph. Tests use this between scenarios."""
    global _singleton
    _singleton = None
