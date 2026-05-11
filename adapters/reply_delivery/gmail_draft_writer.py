"""GmailDraftWriter — writes a Gmail draft on the user's email thread.

Stubbed in phase 1. Real implementation arrives once Gmail OAuth
credentials are placed under `secrets/` per `docs/HANDBOOK.md` section
A. Until then the composition root routes email feedback to
`FilesystemDraftWriter` so the drafter still runs end-to-end against
fixtures.

When implemented, this adapter will:

  1. Load credentials from `secrets/gmail.json` + `secrets/gmail_token.json`.
  2. Use the Gmail API to look up `feedback.gmail_thread_id`.
  3. Build a `drafts.create` request with `body` and the thread's In-Reply-To.
  4. Submit it as a draft (NOT send) so support staff can review + send.
"""

from __future__ import annotations

from domain.draft_reply import DraftReply
from domain.feedback import Feedback


class GmailDraftWriter:
    """Phase-1 placeholder. Constructing this raises so misconfigurations are loud."""

    name: str = "gmail"

    def __init__(self) -> None:
        raise NotImplementedError(
            "GmailDraftWriter is not implemented yet. The composition root "
            "currently routes email feedback to FilesystemDraftWriter. Real "
            "Gmail draft writing arrives once secrets/gmail.json + "
            "secrets/gmail_token.json are placed (see docs/HANDBOOK.md A)."
        )

    def deliver(self, feedback: Feedback, draft: DraftReply) -> None:
        raise NotImplementedError
