"""Read-only note/folder summarization tools for the Obsidian MCP server.

``summarize_note`` and ``summarize_folder`` read bounded content through the hardened
``tools.read_file`` (so format parsing and hidden/protected blocking come for free), then
produce a structured summary via the optional local LLM with deterministic fallback. They
never mutate the vault; folder crawls write a redacted bulk-read receipt.
"""

from __future__ import annotations

from typing import Any

from . import extract, llm, pathsafe
from .config import ObsidianMcpConfig
from .mutations import record_read_receipt
from .tools import (
    ObsidianMcpToolError,
    _extension,
    _hidden_inspection_allowed,
    read_file,
    resolve_safe_path,
)

_SUMMARY_FILE_TYPES = {"md", "txt", "pdf", "docx"}
_RESULT_KEYS = (
    "title",
    "summary",
    "key_points",
    "action_items",
    "decisions",
    "entities",
    "suggested_tags",
    "suggested_links",
)
_MAX_THEMES = 12
_FOLDER_NOTE_CHARS = 4000


def summarize_note(
    config: ObsidianMcpConfig,
    *,
    path: str,
    max_chars: int | None = None,
    summary_style: str = "executive",
    include_action_items: bool = True,
    include_decisions: bool = True,
    include_entities: bool = True,
    operator_mode: bool = False,
    backend: Any = None,
) -> dict[str, Any]:
    cap = min(max_chars or config.max_result_chars, config.max_result_chars)
    read = read_file(config, path=path, max_chars=cap, operator_mode=operator_mode)
    content = str(read.get("content") or "")
    rel = str(read.get("path") or path)
    deterministic = extract.analyze(
        rel,
        content,
        max_chars=cap,
        include_action_items=include_action_items,
        include_decisions=include_decisions,
        include_entities=include_entities,
    )
    result, mode, _reason = llm.summarize(
        config, text=content, deterministic=deterministic, backend=backend
    )
    payload: dict[str, Any] = {
        "path": rel,
        "file_type": read.get("file_type"),
        "summary_style": summary_style,
        "mode": mode,
        "truncated": bool((read.get("metadata") or {}).get("truncated")),
    }
    for key in _RESULT_KEYS:
        payload[key] = result.get(key, deterministic.get(key))
    return payload


def _collect_notes(
    resolved: Any,
    *,
    recursive: bool,
    max_depth: int | None,
    include_hidden: bool,
    allowed_exts: set[str],
    max_files: int,
) -> tuple[list[str], bool]:
    base_depth = len(resolved.path.relative_to(resolved.root).parts) if resolved.path != resolved.root else 0
    iterator = resolved.path.rglob("*") if recursive else resolved.path.iterdir()
    rels: list[str] = []
    truncated = False
    for item in sorted(iterator, key=lambda p: p.as_posix().lower()):
        if pathsafe.symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel, include_hidden=include_hidden):
            continue
        depth = len(item.resolve().relative_to(resolved.root).parts) - base_depth
        if max_depth is not None and depth > max_depth:
            continue
        if item.is_dir() or (_extension(item) or "") not in allowed_exts:
            continue
        if len(rels) >= max_files:
            truncated = True
            break
        rels.append(rel)
    return rels, truncated


def summarize_folder(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    recursive: bool = True,
    max_depth: int | None = 3,
    max_files: int = 100,
    summary_style: str = "project_brief",
    include_file_summaries: bool = True,
    include_themes: bool = True,
    include_action_items: bool = True,
    operator_mode: bool = False,
    principal_kind: str | None = None,
    backend: Any = None,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")
    include_hidden = _hidden_inspection_allowed(config, operator_mode)
    if pathsafe.path_blocked(resolved.relative, include_hidden=include_hidden):
        raise ObsidianMcpToolError("protected_path_blocked")

    allowed_exts = _SUMMARY_FILE_TYPES & {e.lower().lstrip(".") for e in config.allowed_file_types}
    rels, truncated = _collect_notes(
        resolved,
        recursive=recursive,
        max_depth=max_depth,
        include_hidden=include_hidden,
        allowed_exts=allowed_exts,
        max_files=max_files,
    )

    file_summaries: list[dict[str, Any]] = []
    theme_counts: dict[str, int] = {}
    aggregated_actions: list[str] = []
    for rel in rels:
        note = summarize_note(
            config,
            path=rel,
            max_chars=_FOLDER_NOTE_CHARS,
            operator_mode=operator_mode,
            include_action_items=include_action_items,
            backend=backend,
        )
        file_summaries.append(
            {"path": rel, "title": note["title"], "summary": note["summary"], "mode": note["mode"]}
        )
        for tag in note.get("suggested_tags", []) + note.get("entities", []):
            theme_counts[tag] = theme_counts.get(tag, 0) + 1
        if include_action_items:
            aggregated_actions.extend(note.get("action_items", []))

    themes = [t for t, _ in sorted(theme_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:_MAX_THEMES]]
    receipt = record_read_receipt(
        tool_name="vault_summarize_folder",
        scope=resolved.relative or "/",
        principal_kind=principal_kind,
        file_count=len(rels),
        truncated=truncated,
    )
    payload: dict[str, Any] = {
        "root_path": resolved.relative,
        "summary_style": summary_style,
        "files_summarized": len(rels),
        "truncated": truncated,
        "receipt": receipt,
    }
    if include_themes:
        payload["themes"] = themes
    if include_action_items:
        payload["action_items"] = list(dict.fromkeys(aggregated_actions))[:_MAX_THEMES * 2]
    if include_file_summaries:
        payload["file_summaries"] = file_summaries
    return payload
