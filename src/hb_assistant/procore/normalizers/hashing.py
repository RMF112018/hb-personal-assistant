"""Shared hash-only redaction primitive for Phase 04A Procore normalizers.

``hash_summary`` reduces a free-text field to a tiny structural block —
``{"type": "string", "length": int, "hash_prefix": str}`` — and is the single
source of truth for the SHA256[:12] prefix that the V6 schema attestation
(no raw body persisted) and the per-family routing/redaction proofs rely on.
Every Procore normalizer and the live-sync orchestrator import this helper
rather than carrying their own copies.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional


def hash_summary(text: Any) -> Optional[Dict[str, Any]]:
    """Return a hash-only structural summary for a free-text field.

    Never carries the raw text — even short values are reduced to a SHA-256
    prefix so the stop-condition guarantee (no raw body persisted in any
    canonical record) is uniform across normalizers.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)
    encoded = text.encode("utf-8", errors="ignore")
    return {
        "type": "string",
        "length": len(text),
        "hash_prefix": hashlib.sha256(encoded).hexdigest()[:12],
    }


def hash_identifier(value: Any) -> Optional[str]:
    """Return only the SHA-256 hash prefix (12 hex chars) for a PII string.

    Used for email, name, and other short PII identifiers where the
    structural shape is not interesting but the value itself must not
    persist. ``meeting.py`` has a separate 64-char variant for a different
    use case (operator audit / cross-row joins) — that one is intentionally
    not consolidated here.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def person_hash_summary(person: Any) -> Optional[Dict[str, Any]]:
    """Reduce a single person ref to ``{hash_prefix, id}``.

    The Procore person dict carries ``id`` (numeric, opaque Procore id —
    not PII by itself), ``name`` (PII), and optionally ``login`` (email,
    PII) or ``company_name`` (semi-PII). The summary keeps the numeric
    id and hashes the email/name (preferring login when present so the
    same person hashes consistently across endpoints that carry the
    email).
    """
    if not isinstance(person, dict):
        return None
    hash_input = (
        person.get("login")
        if isinstance(person.get("login"), str)
        else person.get("name")
    )
    item: Dict[str, Any] = {"hash_prefix": hash_identifier(hash_input)}
    person_id = person.get("id")
    if isinstance(person_id, int):
        item["id"] = person_id
    return item


__all__ = ["hash_summary", "hash_identifier", "person_hash_summary"]
