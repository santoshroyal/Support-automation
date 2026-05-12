"""JSON-shaped log formatting.

Switches uvicorn (and anything that uses the root logger) from
human-readable lines to one-JSON-object-per-line records. That's what
journald + downstream tooling want: each line is independently
parseable, and a future log shipper (rsyslog → ELK / Loki / Vector
etc.) can ship without re-parsing.

Wired into the FastAPI app via `setup_logging()` called from
`create_app()`. Idempotent — safe to call multiple times.

Why a custom formatter rather than `python-json-logger`: one fewer
dependency to install on the production VM, ~30 lines of code.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """One JSON object per log record. Stable key set; extras land alongside."""

    _STANDARD_KEYS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Anything the caller passed via `logger.info("...", extra={...})`
        # rides along — without this, structured context like trace_id
        # is silently dropped.
        for key, value in record.__dict__.items():
            if key in self._STANDARD_KEYS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(level: str | None = None) -> None:
    """Switch the root logger to JSON output on stderr.

    Level resolution order:
      1. argument
      2. `SUPPORT_AUTOMATION_LOG_LEVEL` env var
      3. INFO
    """
    resolved_level = (
        level
        or os.environ.get("SUPPORT_AUTOMATION_LOG_LEVEL")
        or "INFO"
    ).upper()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    # Replace any handlers added by Python's default or uvicorn — we want
    # exactly one place producing log lines so journald sees one record
    # per event instead of two.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(resolved_level)

    # Bring uvicorn's loggers under the same formatter. Without this,
    # uvicorn keeps its own colourised stream handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        for existing in list(logger.handlers):
            logger.removeHandler(existing)
        logger.propagate = True
