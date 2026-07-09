"""Shared source-structure test helpers."""

from __future__ import annotations

import re

# Absolute-path shapes that must NEVER appear in a client-facing source-structure response.
_ABSOLUTE_MARKERS = ("/Users/", "/Volumes/", "/volume1", "/volume2", "/mnt/", "/home/")
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:[\\/]")


def _string_is_absolute(value: str) -> bool:
    if not value:
        return False
    if any(m in value for m in _ABSOLUTE_MARKERS):
        return True
    if value.startswith(("/", "~/", "\\\\")):
        return True
    return bool(_DRIVE_LETTER.match(value))


def find_absolute_paths(obj: object, path: str = "$") -> list[str]:
    """Recursively collect JSON paths whose string value looks like an absolute host path.

    Only *values* are inspected (dict keys are structural). Returns a list of "json.path=value"
    descriptions; empty means the payload is clean.
    """
    hits: list[str] = []
    if isinstance(obj, str):
        if _string_is_absolute(obj):
            hits.append(f"{path}={obj!r}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits.extend(find_absolute_paths(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hits.extend(find_absolute_paths(v, f"{path}[{i}]"))
    return hits


def assert_no_absolute_paths(obj: object, label: str = "response") -> None:
    """Assert a full response envelope contains no absolute-looking path anywhere (recursively)."""
    hits = find_absolute_paths(obj, f"${label}")
    assert not hits, f"absolute path leaked in {label}: {hits}"
