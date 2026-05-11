"""Shared test fixtures.

Adds the project root to sys.path so tests can import top-level packages
(`domain`, `service_layer`, `adapters`, `entrypoints`) without requiring
an editable install during early development.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
