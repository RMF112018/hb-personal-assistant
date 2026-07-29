"""Privacy fences for raw outputs."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")


def redact_email(text: str) -> str:
    return EMAIL_RE.sub("[REDACTED_EMAIL]", text)


def redact_phone(text: str) -> str:
    return PHONE_RE.sub("[REDACTED_PHONE]", text)


def fence_raw_output(text: str) -> str:
    return redact_phone(redact_email(text))
