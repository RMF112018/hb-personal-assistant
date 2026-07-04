"""Root-key filesystem tools for NAS MCP."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config import NasMcpConfig
from .path_safe import (
    PathAccessError,
    deny_if_blocked,
    is_probably_binary,
    path_display,
    relative_display,
    resolve_under_root,
)
from .redaction import redact_text


class FsToolError(Exception):
    """Denied or invalid filesystem tool call."""


def _root(config: NasMcpConfig, root_key: str) -> Path:
    try:
        return config.root_mount(root_key)
    except KeyError as exc:
        raise FsToolError(str(exc)) from exc


def _resolve(config: NasMcpConfig, root_key: str, relative: str) -> Path:
    root = _root(config, root_key)
    try:
        return resolve_under_root(root, relative)
    except PathAccessError as exc:
        raise FsToolError(str(exc)) from exc


def hb_secure_list(
    *,
    config: NasMcpConfig,
    root_key: str,
    relative_path: str = ".",
    max_entries: int | None = None,
) -> dict[str, Any]:
    root = _root(config, root_key)
    target = _resolve(config, root_key, relative_path)
    deny_if_blocked(target, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
    if not target.exists():
        raise FsToolError("path not found")
    if not target.is_dir():
        raise FsToolError("not a directory")
    limit = min(max_entries or config.max_list_entries, config.max_list_entries)
    entries: list[dict[str, Any]] = []
    with os.scandir(target) as it:
        for entry in it:
            if entry.name.startswith("."):
                continue
            child = Path(entry.path)
            try:
                deny_if_blocked(child, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
            except PathAccessError:
                continue
            rel = relative_display(root, child)
            entries.append(
                {
                    "name": entry.name,
                    "kind": "dir" if entry.is_dir(follow_symlinks=False) else "file",
                    "relative_path": rel,
                    "path_display": path_display(root_key, rel),
                }
            )
            if len(entries) >= limit:
                break
    rel = relative_display(root, target)
    return {
        "root_key": root_key,
        "relative_path": rel,
        "path_display": path_display(root_key, rel),
        "entries": entries,
        "entry_count": len(entries),
        "truncated": len(entries) >= limit,
    }


def hb_secure_stat(*, config: NasMcpConfig, root_key: str, relative_path: str) -> dict[str, Any]:
    root = _root(config, root_key)
    target = _resolve(config, root_key, relative_path)
    deny_if_blocked(target, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
    if not target.exists():
        raise FsToolError("path not found")
    st = target.lstat()
    rel = relative_display(root, target)
    return {
        "root_key": root_key,
        "relative_path": rel,
        "path_display": path_display(root_key, rel),
        "kind": "dir" if target.is_dir() else "file",
        "size": st.st_size,
        "mode": st.st_mode,
    }


def hb_secure_read_excerpt(
    *,
    config: NasMcpConfig,
    root_key: str,
    relative_path: str,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    root = _root(config, root_key)
    target = _resolve(config, root_key, relative_path)
    deny_if_blocked(target, denied_patterns=config.denied_name_patterns, denied_dir_segments=config.denied_dir_segments)
    if not target.is_file():
        raise FsToolError("not a file")
    cap = min(max_bytes or config.max_excerpt_bytes, config.max_excerpt_bytes)
    with target.open("rb") as fh:
        sample = fh.read(cap + 1)
    if is_probably_binary(sample[:4096]):
        raise FsToolError("binary file denied")
    text = sample[:cap].decode("utf-8", errors="replace")
    redacted, applied = redact_text(text)
    rel = relative_display(root, target)
    return {
        "root_key": root_key,
        "relative_path": rel,
        "path_display": path_display(root_key, rel),
        "excerpt": redacted,
        "bytes_returned": len(redacted.encode("utf-8")),
        "truncated": len(sample) > cap,
        "redaction_applied": applied,
    }


def hb_vault_search(*, config: NasMcpConfig, query: str, relative_path: str = ".", limit: int = 25) -> dict[str, Any]:
    listing = hb_secure_list(config=config, root_key="vault", relative_path=relative_path, max_entries=config.max_list_entries)
    q = query.lower()
    matches = [e for e in listing["entries"] if q in e["name"].lower()][: min(limit, config.max_list_entries)]
    return {"root_key": "vault", "query": query, "matches": matches, "match_count": len(matches)}


def hb_vault_read_excerpt(*, config: NasMcpConfig, relative_path: str, max_bytes: int | None = None) -> dict[str, Any]:
    return hb_secure_read_excerpt(config=config, root_key="vault", relative_path=relative_path, max_bytes=max_bytes)


def hb_source_root_search(
    *, config: NasMcpConfig, query: str, root_key: str = "syn-work", relative_path: str = ".", limit: int = 25
) -> dict[str, Any]:
    listing = hb_secure_list(config=config, root_key=root_key, relative_path=relative_path, max_entries=config.max_list_entries)
    q = query.lower()
    matches = [e for e in listing["entries"] if q in e["name"].lower()][: min(limit, config.max_list_entries)]
    return {"root_key": root_key, "query": query, "matches": matches, "match_count": len(matches)}


def hb_source_root_read_excerpt(
    *, config: NasMcpConfig, relative_path: str, root_key: str = "syn-work", max_bytes: int | None = None
) -> dict[str, Any]:
    return hb_secure_read_excerpt(config=config, root_key=root_key, relative_path=relative_path, max_bytes=max_bytes)
