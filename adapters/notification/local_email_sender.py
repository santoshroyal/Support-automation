"""Local-mode digest sender — writes HTML to disk instead of sending email.

Used during local development and during the first 24-48 hours after going
live with real ingestion: lets the operator review what would have been
sent without actually emailing stakeholders. When the digests look right,
flip `notification.mode = "real"` to swap in the SMTP sender.

Each call writes a single HTML file named:
    var/log/digests/<digest_type>_<timestamp>.html

The recipient list is recorded in an HTML comment at the top so the
reviewer can see who would have received the email.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from domain.stakeholder import Stakeholder


class LocalEmailSender:
    name: str = "local_filesystem"

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def send_digest(
        self,
        recipients: Iterable[Stakeholder],
        subject: str,
        html_body: str,
        digest_type: str = "digest",
    ) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{digest_type}_{timestamp}.html"
        target = self._output_dir / filename

        recipient_list = list(recipients)
        recipient_summary = ", ".join(f"{s.name} <{s.email}>" for s in recipient_list)

        target.write_text(
            f"<!--\n"
            f"  digest_type: {digest_type}\n"
            f"  written_at:  {datetime.now(timezone.utc).isoformat()}\n"
            f"  subject:     {subject}\n"
            f"  recipients:  {recipient_summary}\n"
            f"-->\n"
            f"{html_body}",
            encoding="utf-8",
        )
        return target
