"""Frontmatter, properties, and structured-query tools for the Obsidian MCP server.

``vault_read_frontmatter`` and the query tools are read-only; ``vault_update_frontmatter``
mutates through the existing ``mutations.patch_note`` write policy (expected_sha256, backup,
receipt) so frontmatter edits get the same guarantees as any other write. ``vault_dataview_query``
is a safe structured query (a fixed set of operators) — it never executes arbitrary Dataview code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import mdutil, pathsafe
from .config import ObsidianMcpConfig
from .mutations import patch_note, sha256_file, sha256_text
from .tools import (
    ObsidianMcpToolError,
    _extension,
    _hidden_inspection_allowed,
    _utc_from_timestamp,
    resolve_safe_path,
)

_QUERY_OPS = {"eq", "neq", "contains", "exists", "missing", "before", "after"}
_MAX_RESULTS = 500


def _read_md(config: ObsidianMcpConfig, path: str, *, operator_mode: bool) -> Any:
    resolved = resolve_safe_path(config, path, must_exist=True)
    if pathsafe.path_blocked(resolved.relative, include_hidden=_hidden_inspection_allowed(config, operator_mode)):
        raise ObsidianMcpToolError("protected_path_blocked")
    if not resolved.path.is_file():
        raise ObsidianMcpToolError("path_is_not_file")
    if (_extension(resolved.path) or "") != "md":
        raise ObsidianMcpToolError("markdown_only")
    return resolved


def read_frontmatter(config: ObsidianMcpConfig, *, path: str, operator_mode: bool = False) -> dict[str, Any]:
    resolved = _read_md(config, path, operator_mode=operator_mode)
    text = resolved.path.read_text(encoding="utf-8", errors="replace")
    fm, body = mdutil.split_frontmatter(text)
    return {
        "path": resolved.relative,
        "has_frontmatter": fm is not None,
        "frontmatter": fm or {},
        "body_sha256": sha256_text(body),
        "file_sha256": sha256_file(resolved.path),
    }


def _build_updated(text: str, updates: dict[str, Any], *, merge_tags: bool) -> tuple[str, dict[str, Any]]:
    fm, body = mdutil.split_frontmatter(text)
    base: dict[str, Any] = dict(fm) if fm else {}
    new_fm: dict[str, Any] = dict(base)
    for key, value in updates.items():
        if key == "tags" and merge_tags and isinstance(value, list):
            existing = mdutil.frontmatter_tags(base)
            incoming = [str(t).strip().lstrip("#") for t in value if str(t).strip()]
            new_fm["tags"] = list(dict.fromkeys([*existing, *incoming]))
        else:
            new_fm[key] = value
    dumped = yaml.safe_dump(new_fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n{body.lstrip(chr(10))}", new_fm


def update_frontmatter(
    config: ObsidianMcpConfig,
    *,
    path: str,
    updates: dict[str, Any],
    merge_tags: bool = True,
    expected_sha256: str,
    backup_before_replace: bool = True,
    operator_mode: bool = False,
    principal_kind: str | None = None,
) -> dict[str, Any]:
    if not isinstance(updates, dict) or not updates:
        raise ObsidianMcpToolError("frontmatter_updates_required")
    resolved = _read_md(config, path, operator_mode=operator_mode)
    current_sha = sha256_file(resolved.path)
    if not expected_sha256:
        raise ObsidianMcpToolError("expected_sha256_required")
    if expected_sha256 != current_sha:
        raise ObsidianMcpToolError("sha256_mismatch")
    text = resolved.path.read_text(encoding="utf-8", errors="replace")
    new_content, new_fm = _build_updated(text, updates, merge_tags=merge_tags)
    result = patch_note(
        config,
        path=resolved.relative,
        content=new_content,
        expected_sha256=current_sha,
        caller_surface="mcp_frontmatter",
        tool_name="vault_update_frontmatter",
        principal_kind=principal_kind,
    )
    result["frontmatter"] = new_fm
    return result


# ---------------------------------------------------------------------------
# Read-only structured search over frontmatter.
# ---------------------------------------------------------------------------
def _iter_notes(config: ObsidianMcpConfig, root_path: str, *, operator_mode: bool, limit: int) -> list[Any]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")
    include_hidden = _hidden_inspection_allowed(config, operator_mode)
    if pathsafe.path_blocked(resolved.relative, include_hidden=include_hidden):
        raise ObsidianMcpToolError("protected_path_blocked")
    notes: list[Any] = []
    for item in sorted(resolved.path.rglob("*"), key=lambda p: p.as_posix().lower()):
        if pathsafe.symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel, include_hidden=include_hidden):
            continue
        if item.is_dir() or (_extension(item) or "") != "md":
            continue
        text = item.read_text(encoding="utf-8", errors="replace")
        fm, _body = mdutil.split_frontmatter(text)
        notes.append((rel, item, fm or {}, text))
        if len(notes) >= min(limit, _MAX_RESULTS) * 4:
            break
    return notes


def _note_meta(rel: str, item: Path, fm: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "path": rel,
        "title": mdutil.title_of(rel, text),
        "modified": _utc_from_timestamp(item.stat().st_mtime),
        "tags": mdutil.normalized_tags(mdutil.frontmatter_tags(fm)),
    }


def search_by_properties(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    filters: dict[str, Any] | None = None,
    tags_any: list[str] | None = None,
    tags_all: list[str] | None = None,
    limit: int = 100,
    operator_mode: bool = False,
) -> dict[str, Any]:
    cap = min(max(1, limit), _MAX_RESULTS)
    filters = filters or {}
    any_norm = mdutil.normalized_tags(tags_any or [])
    all_norm = mdutil.normalized_tags(tags_all or [])
    results: list[dict[str, Any]] = []
    for rel, item, fm, text in _iter_notes(config, root_path, operator_mode=operator_mode, limit=cap):
        if any(str(fm.get(k)) != str(v) for k, v in filters.items()):
            continue
        note_tags = mdutil.normalized_tags(mdutil.frontmatter_tags(fm))
        if any_norm and not any(t in note_tags for t in any_norm):
            continue
        if all_norm and not all(t in note_tags for t in all_norm):
            continue
        meta = _note_meta(rel, item, fm, text)
        meta["frontmatter"] = {k: fm.get(k) for k in filters} if filters else {}
        results.append(meta)
        if len(results) >= cap:
            break
    return {"root_path": root_path.strip("/"), "count": len(results), "results": results}


def _field_value(fm: dict[str, Any], note: dict[str, Any], field: str) -> Any:
    if field in {"path", "title", "modified", "tags"}:
        return note.get(field)
    return fm.get(field)


def _match_clause(value: Any, op: str, target: Any) -> bool:
    if op == "exists":
        return value is not None
    if op == "missing":
        return value is None
    if value is None:
        return False
    if op == "eq":
        return str(value) == str(target)
    if op == "neq":
        return str(value) != str(target)
    if op == "contains":
        if isinstance(value, list):
            return str(target) in [str(v) for v in value]
        return str(target).lower() in str(value).lower()
    if op == "before":
        return str(value) < str(target)
    if op == "after":
        return str(value) > str(target)
    return False


def dataview_query(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    where: list[dict[str, Any]] | None = None,
    select: list[str] | None = None,
    limit: int = 100,
    operator_mode: bool = False,
) -> dict[str, Any]:
    cap = min(max(1, limit), _MAX_RESULTS)
    clauses = where or []
    for clause in clauses:
        if clause.get("op") not in _QUERY_OPS:
            raise ObsidianMcpToolError("unsupported_query_op")
    fields = select or ["path", "title", "modified"]
    rows: list[dict[str, Any]] = []
    for rel, item, fm, text in _iter_notes(config, root_path, operator_mode=operator_mode, limit=cap):
        note = _note_meta(rel, item, fm, text)
        ok = True
        for clause in clauses:
            value = _field_value(fm, note, str(clause.get("field")))
            if not _match_clause(value, str(clause.get("op")), clause.get("value")):
                ok = False
                break
        if not ok:
            continue
        rows.append({f: _field_value(fm, note, f) for f in fields})
        if len(rows) >= cap:
            break
    return {"root_path": root_path.strip("/"), "count": len(rows), "select": fields, "rows": rows}
