"""Phase 10 V50 — deterministic duplicate group keys for candidate lifecycle.

Computes a stable ``duplicate_group_key`` for any candidate/action subject using ordered
fallbacks (see ``references/duplicate_merge_contract.md``). The key NEVER includes raw text:
only already-redacted titles are normalized + hashed, alongside hashes/codes/keys the system
already produced. The key is what merge/suppression group on, so it must be deterministic across
replay and identical for genuinely-recurring same-source candidates.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

_WS_RE = re.compile(r"\s+")


def _norm_title_hash(title_redacted: Optional[str]) -> Optional[str]:
    """Hash of an already-redacted title after case/whitespace normalization (raw-safe).

    Returns None when there is no title, so the caller falls through to the next basis
    instead of grouping unrelated untitled rows together.
    """
    if not title_redacted:
        return None
    norm = _WS_RE.sub(" ", str(title_redacted).strip().lower())
    if not norm:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def duplicate_group_key(
    *,
    subject_type: str,
    subject_id: str,
    family: Optional[str] = None,
    project_key: Optional[str] = None,
    title_redacted: Optional[str] = None,
    due_bucket: Optional[str] = None,
    stable_key: Optional[str] = None,
    source_refs: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Return a deterministic duplicate group key via ordered fallbacks.

    Priority:
      1. ``src:{source_family}:{source_ref_hash}`` (first source ref, ordered deterministically)
      2. ``key:{stable_key}`` (task/commitment stable key)
      3. ``ttl:{family}:{project_key}:{normalized_redacted_title_hash}:{due_bucket}``
      4. ``one:{subject_type}:{subject_id}`` (last-resort singleton)

    Never hashes raw text; only the already-redacted title is normalized + hashed.
    """
    refs = source_refs or []
    if refs:
        # Deterministic pick: lowest (family, hash) pair so replay is stable regardless of order.
        keyed = sorted(
            (
                (str(r.get("source_family") or ""), str(r.get("source_ref_hash") or ""))
                for r in refs
                if r.get("source_ref_hash")
            )
        )
        if keyed:
            fam, h = keyed[0]
            return f"src:{fam}:{h}"

    if stable_key:
        return f"key:{stable_key}"

    title_hash = _norm_title_hash(title_redacted)
    if title_hash:
        return (
            f"ttl:{family or '?'}:{project_key or '?'}:{title_hash}:{due_bucket or 'none'}"
        )

    return f"one:{subject_type}:{subject_id}"
