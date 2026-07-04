"""JSONL audit writer for NAS MCP tool calls."""

from __future__ import annotations

import contextlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class NasMcpAuditWriter:
    def __init__(self, audit_dir: Path) -> None:
        self._audit_dir = audit_dir

    def write(self, event: dict[str, Any]) -> Path:
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now(UTC).strftime("%Y%m%d")
        path = self._audit_dir / f"mcp-audit-{day}.jsonl"
        payload = dict(event)
        payload.setdefault("request_id", uuid.uuid4().hex)
        payload.setdefault("timestamp_utc", datetime.now(UTC).isoformat())
        payload.setdefault("client_mode", "nas_readonly_streamable_http")
        payload.setdefault("nas_readonly", True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
        with contextlib.suppress(OSError):
            path.chmod(0o600)
        return path
