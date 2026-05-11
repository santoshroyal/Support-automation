"""Port for sending stakeholder digest emails."""

from __future__ import annotations

from typing import Iterable, Protocol

from domain.stakeholder import Stakeholder


class NotificationSenderPort(Protocol):
    def send_digest(
        self,
        recipients: Iterable[Stakeholder],
        subject: str,
        html_body: str,
        digest_type: str = "digest",
    ) -> object:
        """Deliver `html_body` to every recipient and return an
        adapter-specific result (Path for the local sender, count for SMTP).
        Raises if the send itself fails — the use case logs the error.
        """
        ...
