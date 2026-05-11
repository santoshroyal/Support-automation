"""Notification adapters — implementations of NotificationSenderPort.

Phase-1 ships two:

  * SmtpEmailSender    — sends real email via SMTP.
  * LocalEmailSender   — writes the rendered HTML to var/log/digests/<ts>.html
                         so the operator can review what would have gone out
                         before flipping notification.mode to "real".
"""
