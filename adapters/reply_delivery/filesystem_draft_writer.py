"""FilesystemDraftWriter — writes each draft as a Markdown file on disk.

Layout:

    var/support_automation/drafts/<YYYY-MM-DD>/<channel>__<external_id>.md

Each file carries YAML frontmatter (so a future tool / dashboard can
parse it back) plus the rendered body and the citation list. Support
staff open the file, copy the body, paste it into Gmail / Play Console
/ App Store Connect, and click send.

For phase 1 this is the default for every channel. The Gmail API
adapter takes over for email feedback once credentials are configured
in `secrets/gmail.json`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from domain.draft_reply import DraftReply
from domain.feedback import Feedback


class FilesystemDraftWriter:
    name: str = "filesystem"

    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root

    def deliver(self, feedback: Feedback, draft: DraftReply) -> Path:
        date_folder = self._output_root / draft.generated_at.astimezone(
            timezone.utc
        ).strftime("%Y-%m-%d")
        date_folder.mkdir(parents=True, exist_ok=True)
        filename = f"{feedback.channel.value}__{feedback.app_slug}__{feedback.external_id}.md"
        target = date_folder / filename
        target.write_text(self._render(feedback, draft), encoding="utf-8")
        return target

    def _render(self, feedback: Feedback, draft: DraftReply) -> str:
        lines = [
            "---",
            f"feedback_id: {feedback.id}",
            f"draft_id: {draft.id}",
            f"app: {feedback.app_slug}",
            f"channel: {feedback.channel.value}",
            f"platform: {feedback.platform.value}",
            f"author: {feedback.author_identifier}",
            f"language_code: {draft.language_code}",
            f"generated_at: {draft.generated_at.isoformat()}",
            "---",
            "",
            f"## Original ({feedback.channel.value} from {feedback.author_identifier})",
            "",
            feedback.raw_text.strip(),
            "",
            "## Draft reply",
            "",
            draft.body.strip(),
            "",
        ]
        if draft.citations:
            lines.append("## Citations")
            lines.append("")
            for index, citation in enumerate(draft.citations, start=1):
                url = f" — {citation.source_url}" if citation.source_url else ""
                lines.append(f"{index}. {citation.source_title}{url}")
                if citation.snippet:
                    lines.append(f"   > {citation.snippet}")
            lines.append("")
        lines.append(f"_Written by support-automation at "
                     f"{datetime.now(timezone.utc).isoformat()}_")
        return "\n".join(lines)
