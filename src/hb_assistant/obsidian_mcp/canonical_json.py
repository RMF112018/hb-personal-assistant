"""Deterministic canonical JSON + checksum helpers for semantic fingerprints.

UTF-8, sorted object keys, sorted set-like arrays; list order preserved for sequences
(e.g. workflow tool steps). Checksum form: ``sha256:<hex>``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(value: Any, *, sort_sets: bool = True) -> Any:
    """Normalize a JSON-like structure for stable hashing.

    - dict keys sorted
    - list of plain scalars (set-like) sorted when ``sort_sets`` and all items are hashable scalars
    - sequence order preserved for lists of objects / mixed structures
    - None retained as null
    """
    if isinstance(value, dict):
        return {k: canonicalize(value[k], sort_sets=sort_sets) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple)):
        items = [canonicalize(v, sort_sets=sort_sets) for v in value]
        if sort_sets and items and all(_is_set_like_scalar(x) for x in items):
            return sorted(items, key=_scalar_sort_key)
        return items
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value)


def _is_set_like_scalar(x: Any) -> bool:
    return isinstance(x, (str, int, float, bool)) or x is None


def _scalar_sort_key(x: Any) -> tuple[int, str]:
    return (0 if x is None else 1, "" if x is None else f"{type(x).__name__}:{x}")


def canonical_json_bytes(value: Any, *, sort_sets: bool = True) -> bytes:
    normalized = canonicalize(value, sort_sets=sort_sets)
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_fingerprint(value: Any, *, prefix: str = "sha256", sort_sets: bool = True) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value, sort_sets=sort_sets)).hexdigest()
    return f"{prefix}:{digest}"
