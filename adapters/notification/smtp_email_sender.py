"""SMTP-based digest sender — used when notification.mode = "real".

Reads SMTP host/port/user from environment (engineer-managed config) and
the password from `secrets/smtp_password`. Sends one multipart message
addressed to the BCC of every stakeholder so individuals don't see each
other's addresses.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

from domain.stakeholder import Stakeholder


class SmtpEmailSender:
    name: str = "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password_path: Path,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password_path = password_path
        self._from_address = from_address
        self._use_tls = use_tls

    def send_digest(
        self,
        recipients: Iterable[Stakeholder],
        subject: str,
        html_body: str,
        digest_type: str = "digest",
    ) -> int:
        recipient_list = [s.email for s in recipients]
        if not recipient_list:
            return 0

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._from_address
        message["To"] = self._from_address  # send to self; everyone goes BCC
        message["Bcc"] = ", ".join(recipient_list)
        message.set_content("Plain-text fallback: open the HTML version of this email.")
        message.add_alternative(html_body, subtype="html")

        password = self._password_path.read_text(encoding="utf-8").strip()

        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            smtp.login(self._username, password)
            smtp.send_message(message)

        return len(recipient_list)
