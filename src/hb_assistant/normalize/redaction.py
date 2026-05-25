"""Redaction and hashing helpers for PII fields in mail/calendar objects.

Per 06_Graph_Integration_Specification:
- Subject: redacted or hashed
- Sender/recipients: domain + hash
- BodyPreview: truncated/redacted
- Location, organizer, attendees: hashed/redacted
- Never store full body or file content.
"""

from __future__ import annotations

import hashlib
from typing import Optional


def hash_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact_subject(subject: Optional[str]) -> Optional[str]:
    if not subject:
        return None
    # Store only hash for traceability; caller can keep original if needed in memory only
    return f"[redacted:{hash_value(subject)}]"


def redact_recipient(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    if "@" not in email:
        return hash_value(email)
    local, domain = email.split("@", 1)
    return f"{hash_value(local)}@{domain}"


def truncate_preview(preview: Optional[str], max_len: int = 120) -> Optional[str]:
    if not preview:
        return None
    if len(preview) <= max_len:
        return preview
    return preview[:max_len] + "..."


def redact_location(location: Optional[str]) -> Optional[str]:
    if not location:
        return None
    return f"[redacted:{hash_value(location)}]"
