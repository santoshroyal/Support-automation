"""Interactive helper for adding a feedback fixture safely.

Why this exists
---------------
Crafting fixture JSON files via shell heredocs or `python -c` one-liners is
copy-paste fragile — invisible characters, indentation, and quoting all bite.
This helper prompts for each field on its own line, writes valid JSON, and
puts the file in the right channel folder.

Usage
-----
    python scripts/add_feedback_fixture.py
        # ↳ interactive prompts

    python scripts/add_feedback_fixture.py --channel gmail
        # ↳ skip the channel prompt

    python scripts/add_feedback_fixture.py --channel gmail --json-file my.json
        # ↳ no prompts; copies my.json into the right folder after validating shape

Run it from the project root.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_BASE = PROJECT_ROOT / "data_fixtures" / "feedback"

CHANNEL_FOLDERS = {
    "gmail": "gmail",
    "google_play": "play",
    "apple_app_store": "apple",
}

# Fields each channel's fixture is expected to have. The helper will prompt
# only for the listed fields; anything not provided is simply omitted from
# the resulting JSON.
GMAIL_FIELDS = [
    ("external_id", "Unique message ID (e.g. msg_2026_05_04_001)", True),
    ("thread_id", "Gmail thread ID", True),
    ("from", "Sender email", True),
    ("subject", "Subject line", True),
    ("body", "Email body (single line; use \\n for line breaks)", True),
    ("received_at", "Timestamp (ISO 8601, e.g. 2026-05-04T08:00:00Z)", True),
    ("language_hint", "Language code (en/hi/ta/...) or blank to skip", False),
    ("app_version", "App version (e.g. 8.3.1) or blank", False),
    ("device", "Device (e.g. Pixel 7) or blank", False),
]

PLAY_FIELDS = [
    ("external_id", "Unique review ID (e.g. play_review_2026_05_04_001)", True),
    ("author", "Reviewer name (or 'A Google user')", True),
    ("star_rating", "Star rating 1-5", True),
    ("text", "Review text", True),
    ("received_at", "Timestamp (ISO 8601)", True),
    ("language_hint", "Language code or blank", False),
    ("app_version", "App version or blank", False),
    ("device_model", "Device model or blank", False),
    ("android_version", "Android version (e.g. 14) or blank", False),
]

APPLE_FIELDS = [
    ("external_id", "Unique review ID (e.g. apple_review_2026_05_04_001)", True),
    ("nickname", "Reviewer nickname", True),
    ("star_rating", "Star rating 1-5", True),
    ("title", "Review title", True),
    ("body", "Review body", True),
    ("received_at", "Timestamp (ISO 8601)", True),
    ("territory", "Territory code (e.g. IND, USA) or blank", False),
    ("language_hint", "Language code or blank", False),
    ("app_version", "App version or blank", False),
]

CHANNEL_FIELDS = {
    "gmail": GMAIL_FIELDS,
    "google_play": PLAY_FIELDS,
    "apple_app_store": APPLE_FIELDS,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add a feedback fixture interactively")
    parser.add_argument(
        "--channel",
        choices=list(CHANNEL_FOLDERS.keys()),
        help="Channel for the new fixture; prompted if omitted",
    )
    parser.add_argument(
        "--json-file",
        type=Path,
        help="Path to an existing JSON file to copy into the right folder (skip prompts)",
    )
    parser.add_argument(
        "--filename",
        help="Filename to use (default: auto-generated from the timestamp + channel)",
    )
    args = parser.parse_args(argv)

    channel = args.channel or _prompt_channel()
    target_folder = FIXTURES_BASE / CHANNEL_FOLDERS[channel]
    target_folder.mkdir(parents=True, exist_ok=True)

    if args.json_file is not None:
        payload = _load_json_file(args.json_file)
    else:
        payload = _prompt_payload(channel)

    filename = args.filename or _suggest_filename(channel, payload)
    target_path = target_folder / filename

    if target_path.exists():
        confirm = input(f"{target_path} already exists. Overwrite? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.", file=sys.stderr)
            return 1

    target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Written: {target_path}")
    return 0


def _prompt_channel() -> str:
    print("Which channel?")
    keys = list(CHANNEL_FOLDERS.keys())
    for index, key in enumerate(keys, start=1):
        print(f"  {index}. {key}")
    while True:
        raw = input("Pick 1-3: ").strip()
        if raw in {"1", "2", "3"}:
            return keys[int(raw) - 1]
        if raw in CHANNEL_FOLDERS:
            return raw
        print("Invalid choice. Try again.")


def _prompt_payload(channel: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    print(f"\nEntering fields for channel '{channel}'.")
    print("Press Enter on optional fields to skip them.\n")
    for field_name, prompt_text, required in CHANNEL_FIELDS[channel]:
        while True:
            raw = input(f"{prompt_text}: ").strip()
            if not raw:
                if required:
                    print("This field is required.")
                    continue
                break
            payload[field_name] = _coerce(field_name, raw)
            break
    return payload


def _coerce(field_name: str, raw: str) -> Any:
    """Convert string input to the expected Python type for known numeric fields."""
    if field_name == "star_rating":
        try:
            value = int(raw)
        except ValueError as exc:
            raise SystemExit(f"star_rating must be 1-5, got {raw!r}") from exc
        if not 1 <= value <= 5:
            raise SystemExit(f"star_rating must be 1-5, got {value}")
        return value
    if field_name == "received_at":
        # Validate it parses; store as the original string so the fixture stays
        # in the canonical ISO 8601 form the operator typed.
        _parse_iso(raw)
    if field_name == "body":
        return raw.replace("\\n", "\n")
    return raw


def _parse_iso(value: str) -> datetime:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _suggest_filename(channel: str, payload: dict[str, Any]) -> str:
    received = payload.get("received_at", datetime.now(timezone.utc).isoformat())
    parsed = _parse_iso(str(received))
    stamp = parsed.strftime("%Y%m%d_%H%M%S")
    label = "fixture"
    if channel == "gmail" and "subject" in payload:
        label = _slug(payload["subject"])
    elif channel == "google_play" and "text" in payload:
        label = _slug(payload["text"][:40])
    elif channel == "apple_app_store" and "title" in payload:
        label = _slug(payload["title"])
    return f"{stamp}_{label}.json"


def _slug(text: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in text)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned[:40] or "fixture"


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object at the top level")
    return data


if __name__ == "__main__":
    sys.exit(main())
