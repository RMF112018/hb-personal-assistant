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


__all__ = ["hash_summary"]
