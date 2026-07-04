"""Path safety for NAS MCP filesystem tools (no obsidian_mcp imports)."""

from __future__ import annotations

import os
from pathlib import Path


class PathAccessError(Exception):
    """Denied or invalid relative path under a configured root."""


def validate_relative_under_root(source_root: Path, rel: str, *, kind: str = "path") -> Path:
    raw = str(rel).strip().replace("\\", "/")
    if not raw:
        raise PathAccessError(f"empty include-{kind}")
    p = Path(raw)
    if p.is_absolute():
        raise PathAccessError(f"absolute include-{kind} rejected")
    parts = [seg for seg in p.parts if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        raise PathAccessError(f"'..' traversal in include-{kind} rejected")
    joined = source_root.joinpath(*parts) if parts else source_root
    root_n = os.path.normpath(str(source_root))
    cand_n = os.path.normpath(str(joined))
    if cand_n != root_n and not cand_n.startswith(root_n + os.sep):
        raise PathAccessError(f"include-{kind} escapes source-root")
    return joined


def resolve_under_root(root: Path, relative: str) -> Path:
    target = validate_relative_under_root(root, relative)
    root_resolved = Path(os.path.realpath(root))
    if target.exists() or target.is_symlink():
        resolved = Path(os.path.realpath(target))
        root_s = os.path.normpath(str(root_resolved))
        resolved_s = os.path.normpath(str(resolved))
        if resolved_s != root_s and not resolved_s.startswith(root_s + os.sep):
            raise PathAccessError("symlink escapes root")
    return target


def path_display(root_key: str, relative: str) -> str:
    rel = relative.strip().replace("\\", "/")
    if rel in ("", "."):
        return root_key
    return f"{root_key}/{rel}"


def deny_if_blocked(path: Path, *, denied_patterns: tuple[str, ...], denied_dir_segments: tuple[str, ...]) -> None:
    parts = path.parts
    lowered = "/".join(parts).lower()
    for seg in denied_dir_segments:
        if seg.lower() in (p.lower() for p in parts):
            raise PathAccessError(f"denied directory segment: {seg}")
    for pattern in denied_patterns:
        if pattern.lower() in lowered:
            raise PathAccessError(f"denied path pattern: {pattern}")
    if lowered.endswith(".enc"):
        raise PathAccessError("denied .enc blob")


def is_probably_binary(sample: bytes) -> bool:
    if b"\x00" in sample:
        return True
    text = sample.decode("utf-8", errors="ignore")
    if not text and sample:
        return True
    non_printable = sum(1 for ch in text if ord(ch) < 9 or (13 < ord(ch) < 32))
    return non_printable > max(3, len(text) // 10)


def relative_display(root: Path, target: Path) -> str:
    root_n = os.path.normpath(str(root))
    cand_n = os.path.normpath(str(target))
    if cand_n == root_n:
        return "."
    prefix = root_n + os.sep
    if cand_n.startswith(prefix):
        return cand_n[len(prefix) :]
    raise PathAccessError("path escapes root")
