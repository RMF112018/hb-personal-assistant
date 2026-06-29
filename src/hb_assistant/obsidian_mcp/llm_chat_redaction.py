"""Redaction and truncation for LLM chat ingest."""

from __future__ import annotations

import re
from dataclasses import dataclass

_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE)
_TOKEN_RE = re.compile(
    r"(access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|"
    r"x[_-]?api[_-]?key|password|passwd|private[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_AWS_KEY_RE = re.compile(r"\b(AKIA[0-9A-Z]{16})\b")
_GENERIC_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9\-]{10,})"
)
_CREDENTIAL_PARAM_RE = re.compile(
    r"([?&](?:sig|signature|token|access_token|api_key|apikey|key)=[^&#\s\"']+)",
    re.IGNORECASE,
)

_REDACT_REPLACEMENT = "[REDACTED]"


@dataclass
class IngestResult:
    text: str
    char_count: int
    truncated: bool
    redaction_count: int


def redact_text(text: str) -> tuple[str, int]:
    count = 0
    out = text

    for pattern in (_BEARER_RE, _TOKEN_RE, _AWS_KEY_RE, _GENERIC_SECRET_RE, _CREDENTIAL_PARAM_RE):
        matches = list(pattern.finditer(out))
        count += len(matches)
        out = pattern.sub(_REDACT_REPLACEMENT, out)

    return out, count


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n\n[TRUNCATED]", True


def ingest_text(text: str, *, max_chars: int, redact: bool = True) -> IngestResult:
    raw = text or ""
    if redact:
        redacted, redaction_count = redact_text(raw)
    else:
        redacted, redaction_count = raw, 0
    truncated_text, truncated = truncate_text(redacted, max_chars)
    return IngestResult(
        text=truncated_text,
        char_count=len(truncated_text),
        truncated=truncated,
        redaction_count=redaction_count,
    )
