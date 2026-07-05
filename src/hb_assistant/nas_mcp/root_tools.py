"""Read-only generic root tools for home/work."""

from __future__ import annotations

from typing import Any

from .config import NasMcpConfig
from .file_readers import FileReadError, read_bounded_file
from .fs_tools import FsToolError, hb_secure_list, hb_secure_read_excerpt, hb_secure_stat
from .path_safe import PathAccessError, path_display
from .root_policy import READ_ONLY_ROOTS, RootPolicyError, assert_read


def _normalize(root_key: str, relative_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    rel = payload.get("relative_path", relative_path)
    out = dict(payload)
    out["root_key"] = root_key
    out.setdefault("path_display", path_display(root_key, str(rel)))
    return out


def hb_root_list(*, config: NasMcpConfig, root_key: str, relative_path: str = ".", max_entries: int | None = None) -> dict[str, Any]:
    if root_key not in READ_ONLY_ROOTS:
        raise RootPolicyError(f"hb_root_list unsupported root_key: {root_key}")
    assert_read(config, root_key)
    result = hb_secure_list(config=config, root_key=root_key, relative_path=relative_path, max_entries=max_entries)
    return _normalize(root_key, relative_path, result)


def hb_root_stat(*, config: NasMcpConfig, root_key: str, relative_path: str) -> dict[str, Any]:
    if root_key not in READ_ONLY_ROOTS:
        raise RootPolicyError(f"hb_root_stat unsupported root_key: {root_key}")
    assert_read(config, root_key)
    result = hb_secure_stat(config=config, root_key=root_key, relative_path=relative_path)
    return _normalize(root_key, relative_path, result)


def hb_root_search(
    *, config: NasMcpConfig, root_key: str, query: str, relative_path: str = ".", limit: int = 25
) -> dict[str, Any]:
    if root_key not in READ_ONLY_ROOTS:
        raise RootPolicyError(f"hb_root_search unsupported root_key: {root_key}")
    assert_read(config, root_key)
    listing = hb_root_list(config=config, root_key=root_key, relative_path=relative_path)
    q = query.lower()
    matches = [e for e in listing["entries"] if q in e["name"].lower()][: min(limit, config.max_search_results)]
    return {"root_key": root_key, "query": query, "matches": matches, "match_count": len(matches)}


def hb_root_read_excerpt(
    *, config: NasMcpConfig, root_key: str, relative_path: str, max_bytes: int | None = None
) -> dict[str, Any]:
    if root_key not in READ_ONLY_ROOTS:
        raise RootPolicyError(f"hb_root_read_excerpt unsupported root_key: {root_key}")
    assert_read(config, root_key)
    result = hb_secure_read_excerpt(config=config, root_key=root_key, relative_path=relative_path, max_bytes=max_bytes)
    return _normalize(root_key, relative_path, result)


def hb_root_read_file(
    *, config: NasMcpConfig, root_key: str, relative_path: str, max_chars: int | None = None
) -> dict[str, Any]:
    if root_key not in READ_ONLY_ROOTS:
        raise RootPolicyError(f"hb_root_read_file unsupported root_key: {root_key}")
    spec = assert_read(config, root_key)
    try:
        payload = read_bounded_file(
            config=config, root=spec.mount, relative_path=relative_path, max_chars=max_chars
        )
    except (FileReadError, PathAccessError) as exc:
        raise FsToolError(str(exc)) from exc
    rel = relative_path.strip().replace("\\", "/") or "."
    return {"root_key": root_key, "relative_path": rel, "path_display": path_display(root_key, rel), **payload}
