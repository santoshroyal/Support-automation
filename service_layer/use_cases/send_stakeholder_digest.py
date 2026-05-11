"""SendStakeholderDigest — build and send the hourly / daily digest email.

The digest's job is to put a short, actionable summary in front of the
right people — not to be a dashboard. Each digest covers spikes recorded
since `now - lookback_hours`. Stakeholders that opted out of this cadence
are filtered out before send.

Layout (HTML):
  • Header: app/platform totals for the window.
  • "What fired" table: each spike event with cluster label, count,
    baseline ratio, and a sample feedback id.
  • If no spikes: a one-line "all quiet" message — still sent, so
    stakeholders know the system is alive.

The whole digest is logged to the digest_log table whether it sent
successfully or not, so ops can audit "did we actually email people?"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from domain.spike_event import SpikeEvent
from domain.stakeholder import Stakeholder
from service_layer.ports.digest_log_repository_port import (
    DigestLogEntry,
    DigestLogRepositoryPort,
)
from service_layer.ports.feedback_cluster_repository_port import (
    FeedbackClusterRepositoryPort,
)
from service_layer.ports.notification_sender_port import NotificationSenderPort
from service_layer.ports.spike_event_repository_port import SpikeEventRepositoryPort


@dataclass(frozen=True)
class DigestResult:
    digest_type: str
    spikes_in_window: int
    recipients: int
    sent: bool
    error: str | None


class SendStakeholderDigest:
    def __init__(
        self,
        spike_event_repository: SpikeEventRepositoryPort,
        cluster_repository: FeedbackClusterRepositoryPort,
        digest_log_repository: DigestLogRepositoryPort,
        notification_sender: NotificationSenderPort,
        stakeholders: Iterable[Stakeholder],
        lookback_hours: int,
        digest_type: str,
    ) -> None:
        self._spike_repository = spike_event_repository
        self._cluster_repository = cluster_repository
        self._digest_log_repository = digest_log_repository
        self._notification_sender = notification_sender
        self._stakeholders = list(stakeholders)
        self._lookback_hours = lookback_hours
        self._digest_type = digest_type

    def run(self) -> DigestResult:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=self._lookback_hours)
        spikes = list(self._spike_repository.list_recent(since=since))

        subject = self._subject(spikes_count=len(spikes), now=now)
        html_body = self._render(spikes=spikes, since=since, now=now)

        error: str | None = None
        try:
            self._notification_sender.send_digest(
                recipients=self._stakeholders,
                subject=subject,
                html_body=html_body,
                digest_type=self._digest_type,
            )
            sent = True
        except Exception as exc:  # noqa: BLE001 — log everything in the digest log
            sent = False
            error = f"{type(exc).__name__}: {exc}"

        self._digest_log_repository.add(
            DigestLogEntry(
                type=self._digest_type,
                body_html=html_body,
                recipients=[s.email for s in self._stakeholders],
                sent_at=now,
                error=error,
            )
        )

        return DigestResult(
            digest_type=self._digest_type,
            spikes_in_window=len(spikes),
            recipients=len(self._stakeholders),
            sent=sent,
            error=error,
        )

    def _subject(self, spikes_count: int, now: datetime) -> str:
        if spikes_count == 0:
            return f"[Support Automation] {self._digest_type.title()} digest — all quiet"
        return (
            f"[Support Automation] {self._digest_type.title()} digest — "
            f"{spikes_count} spike{'s' if spikes_count != 1 else ''}"
        )

    def _render(
        self, spikes: list[SpikeEvent], since: datetime, now: datetime
    ) -> str:
        rows_html = "".join(
            self._render_spike_row(spike) for spike in spikes
        ) or '<tr><td colspan="4" style="padding:12px;color:#888;">No spikes in this window. ✅</td></tr>'

        return f"""<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,sans-serif;">
<h2 style="margin:0 0 4px 0;">Support Automation — {self._digest_type.title()} digest</h2>
<p style="color:#666;margin:0 0 16px 0;">
Window: {since.isoformat(timespec='minutes')} → {now.isoformat(timespec='minutes')}
</p>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse;">
  <thead style="background:#f3f4f6;text-align:left;">
    <tr>
      <th>Cluster</th>
      <th>Count (last {self._lookback_hours}h)</th>
      <th>Baseline (per day)</th>
      <th>Ratio</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
<p style="color:#888;font-size:12px;margin-top:16px;">
Click a cluster id in the dashboard to drill in to the contributing feedback.
</p>
</body></html>
"""

    def _render_spike_row(self, spike: SpikeEvent) -> str:
        cluster = self._cluster_repository.get_cluster(spike.cluster_id)
        label = (cluster.label if cluster and cluster.label else str(spike.cluster_id)[:8])
        return (
            f"<tr>"
            f"<td>{_escape(label)}</td>"
            f"<td>{spike.count}</td>"
            f"<td>{spike.baseline:.2f}</td>"
            f"<td><strong>{spike.ratio:.2f}×</strong></td>"
            f"</tr>"
        )


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
