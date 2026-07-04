"""Bounded redaction for NAS MCP excerpts."""

from __future__ import annotations

import re

_REDACT_PATTERNS = (
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I), "[REDACTED_BEARER]"),
    (re.compile(r"(?i)(access_token|refresh_token|id_token|client_secret)\s*[:=]\s*\S+"), "[REDACTED_TOKEN_FIELD]"),
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_API_KEY]"),
)


def redact_text(text: str) -> tuple[str, bool]:
    redacted = text
    applied = False
    for pattern, repl in _REDACT_PATTERNS:
        new, count = pattern.subn(repl, redacted)
        if count:
            applied = True
            redacted = new
    return redacted, applied
