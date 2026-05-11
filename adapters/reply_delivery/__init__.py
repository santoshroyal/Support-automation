"""Reply-delivery adapters — where a generated draft lands for human review.

Two implementations in phase 1:

  * FilesystemDraftWriter — writes the draft as a Markdown file under
    var/support_automation/drafts/<date>/<feedback_id>.md. Used for
    store reviews (Play / Apple), since the Play Developer API requires
    going through the console anyway. Also the phase-1 default for
    email channels — Gmail integration is deferred until credentials
    are configured (see docs/HANDBOOK.md section A).

  * GmailDraftWriter (planned) — writes a Gmail draft on the existing
    thread via the Gmail API. Requires OAuth credentials in
    secrets/gmail.json. The composition root will pick this when
    `feedback.gmail.mode = real` in settings.
"""
