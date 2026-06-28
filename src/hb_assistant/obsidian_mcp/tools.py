"""Filesystem-mode tools for the UI-managed Obsidian MCP server."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.files.parsers.docx import DOCXParser
from hb_assistant.files.parsers.pdf import PDFParser

from . import pathsafe
from .config import ObsidianMcpConfig


class ObsidianMcpToolError(ValueError):
    """Safe, user-displayable tool error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class ResolvedPath:
    root: Path
    path: Path
    relative: str


def _utc_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).replace(microsecond=0).isoformat()


def _normalize_relative(path: str | None) -> str:
    raw = (path or "").strip()
    raw = raw.replace("\\", "/")
    return raw.strip("/")


def resolve_safe_path(config: ObsidianMcpConfig, requested: str | None, *, must_exist: bool = False) -> ResolvedPath:
    raw_requested = (requested or "").strip().replace("\\", "/")
    if Path(raw_requested).is_absolute():
        raise ObsidianMcpToolError("absolute_paths_not_allowed")
    rel = _normalize_relative(requested)
    candidate = Path(rel)
    if rel and any(part in {"..", ""} for part in candidate.parts):
        raise ObsidianMcpToolError("path_traversal_not_allowed")

    root = Path(config.vault_root).expanduser().resolve()
    target = (root / candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ObsidianMcpToolError("path_outside_vault_root") from exc
    if must_exist and not target.exists():
        raise ObsidianMcpToolError("path_not_found")
    relative = "" if target == root else target.relative_to(root).as_posix()
    return ResolvedPath(root=root, path=target, relative=relative)


def _hidden_inspection_allowed(config: ObsidianMcpConfig, operator_mode: bool) -> bool:
    """Hidden/dot paths are inspectable only by a local operator with the opt-in.

    OAuth clients always pass ``operator_mode=False`` so they can never see them.
    The hard protected set stays blocked regardless (enforced in ``pathsafe``).
    """
    return bool(operator_mode and config.curation_operator_hidden_inspection)


def _extension(path: Path) -> str | None:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or None


def _allowed_extensions(config: ObsidianMcpConfig, extensions: list[str] | None = None) -> set[str]:
    base = {e.lower().lstrip(".") for e in config.allowed_file_types}
    if extensions:
        requested = {e.lower().lstrip(".") for e in extensions}
        return {e for e in requested if e in base}
    return base


def _check_size(config: ObsidianMcpConfig, path: Path) -> tuple[bool, int]:
    size = path.stat().st_size
    return size <= config.max_file_mb * 1024 * 1024, size


def list_directory(
    config: ObsidianMcpConfig,
    *,
    path: str = "",
    recursive: bool = False,
    extensions: list[str] | None = None,
    max_depth: int | None = None,
    operator_mode: bool = False,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")
    if pathsafe.path_blocked(resolved.relative, include_hidden=_hidden_inspection_allowed(config, operator_mode)):
        raise ObsidianMcpToolError("protected_path_blocked")

    include_hidden = _hidden_inspection_allowed(config, operator_mode)
    allowed_exts = _allowed_extensions(config, extensions)
    files: list[dict[str, Any]] = []
    base_depth = len(resolved.path.relative_to(resolved.root).parts) if resolved.path != resolved.root else 0

    iterator = resolved.path.rglob("*") if recursive else resolved.path.iterdir()
    for item in sorted(iterator, key=lambda p: p.as_posix().lower()):
        if item.is_symlink():
            try:
                item.resolve().relative_to(resolved.root)
            except ValueError:
                continue
        rel_path = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel_path, include_hidden=include_hidden):
            continue
        depth = len(item.resolve().relative_to(resolved.root).parts) - base_depth
        if max_depth is not None and depth > max_depth:
            continue
        ext = _extension(item)
        item_type = "directory" if item.is_dir() else "file"
        if item_type == "file" and allowed_exts and (ext or "") not in allowed_exts:
            continue
        stat = item.stat()
        files.append(
            {
                "path": rel_path,
                "name": item.name,
                "extension": ext,
                "type": item_type,
                "size_bytes": stat.st_size if item.is_file() else None,
                "modified_at": _utc_from_timestamp(stat.st_mtime),
            }
        )

    return {"root": str(resolved.root), "path": resolved.relative, "files": files}


def _markdown_heading_section(content: str, heading: str) -> str | None:
    wanted = heading.strip().lower().lstrip("#").strip()
    lines = content.splitlines()
    start_idx: int | None = None
    start_level = 0
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    for idx, line in enumerate(lines):
        match = heading_re.match(line)
        if not match:
            continue
        level = len(match.group(1))
        label = match.group(2).strip().lower()
        if start_idx is None and label == wanted:
            start_idx = idx
            start_level = level
            continue
        if start_idx is not None and level <= start_level:
            return "\n".join(lines[start_idx:idx]).strip()
    if start_idx is None:
        return None
    return "\n".join(lines[start_idx:]).strip()


def _read_text(path: Path, max_chars: int) -> tuple[str, bool]:
    data = path.read_text(encoding="utf-8", errors="replace")
    truncated = len(data) > max_chars
    return data[:max_chars], truncated


def _read_pdf(path: Path, max_chars: int, start_page: int | None, end_page: int | None) -> dict[str, Any]:
    if start_page is None and end_page is None:
        meta = PDFParser().parse(path, max_chars=max_chars)
        content = str(meta.get("text_excerpt") or "")[:max_chars]
        return {
            "content": content,
            "metadata": {
                "pages": meta.get("page_count"),
                "truncated": bool(meta.get("char_count", 0) >= max_chars),
                "extraction_method": meta.get("extraction_engine"),
                "failure_code": meta.get("failure_code"),
            },
        }
    try:
        import pdfplumber
    except ImportError as exc:
        raise ObsidianMcpToolError("pdf_page_range_dependency_missing") from exc
    parts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        start = max(1, start_page or 1)
        end = min(page_count, end_page or page_count)
        for page in pdf.pages[start - 1 : end]:
            parts.append(page.extract_text() or "")
            if sum(len(part) for part in parts) >= max_chars:
                break
    content = "\n".join(parts)[:max_chars]
    return {
        "content": content,
        "metadata": {
            "pages": page_count,
            "start_page": start,
            "end_page": end,
            "truncated": sum(len(part) for part in parts) > max_chars,
            "extraction_method": "pdfplumber_page_range",
        },
    }


def read_file(
    config: ObsidianMcpConfig,
    *,
    path: str,
    start_page: int | None = None,
    end_page: int | None = None,
    section: str | None = None,
    max_chars: int | None = None,
    operator_mode: bool = False,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, path, must_exist=True)
    if pathsafe.path_blocked(resolved.relative, include_hidden=_hidden_inspection_allowed(config, operator_mode)):
        raise ObsidianMcpToolError("protected_path_blocked")
    if not resolved.path.is_file():
        raise ObsidianMcpToolError("path_is_not_file")
    ext = _extension(resolved.path) or ""
    if ext not in config.allowed_file_types:
        raise ObsidianMcpToolError("unsupported_file_type")
    ok_size, size = _check_size(config, resolved.path)
    if not ok_size:
        raise ObsidianMcpToolError("file_exceeds_size_cap")

    cap = min(max_chars or config.max_result_chars, config.max_result_chars)
    metadata: dict[str, Any] = {"truncated": False}

    if ext in {"md", "txt"}:
        content, truncated = _read_text(resolved.path, cap if not section else max(size, cap))
        if section and ext == "md":
            full_text = resolved.path.read_text(encoding="utf-8", errors="replace")
            section_text = _markdown_heading_section(full_text, section)
            if section_text is None:
                raise ObsidianMcpToolError("section_not_found")
            truncated = len(section_text) > cap
            content = section_text[:cap]
            metadata["section"] = section
        metadata["truncated"] = truncated
    elif ext == "pdf":
        pdf = _read_pdf(resolved.path, cap, start_page, end_page)
        content = pdf["content"]
        metadata.update(pdf["metadata"])
    elif ext == "docx":
        meta = DOCXParser().parse(resolved.path, max_chars=cap)
        content = str(meta.get("text_excerpt") or "")[:cap]
        metadata.update(
            {
                "truncated": bool(meta.get("char_count", 0) >= cap),
                "extraction_method": "python-docx",
                "paragraph_count": meta.get("paragraph_count"),
                "table_count": meta.get("table_count"),
                "failure_code": meta.get("failure_code"),
            }
        )
    else:
        raise ObsidianMcpToolError("unsupported_file_type")

    return {"path": resolved.relative, "file_type": ext, "content": content, "metadata": metadata}


def _iter_search_files(
    config: ObsidianMcpConfig,
    scope: str | None,
    file_types: list[str] | None,
    *,
    operator_mode: bool = False,
) -> list[Path]:
    resolved = resolve_safe_path(config, scope or "", must_exist=True)
    include_hidden = _hidden_inspection_allowed(config, operator_mode)
    if pathsafe.path_blocked(resolved.relative, include_hidden=include_hidden):
        raise ObsidianMcpToolError("protected_path_blocked")
    allowed = _allowed_extensions(config, file_types)
    root = resolved.path
    candidates = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    out: list[Path] = []
    for path in candidates:
        try:
            rel = path.resolve().relative_to(resolved.root).as_posix()
        except ValueError:
            continue
        if pathsafe.path_blocked(rel, include_hidden=include_hidden):
            continue
        ext = _extension(path) or ""
        if ext in allowed:
            out.append(path)
    return sorted(out, key=lambda p: p.as_posix().lower())


def _snippet(content: str, query: str, max_len: int = 240) -> str:
    low = content.lower()
    q = query.lower()
    idx = low.find(q)
    if idx < 0:
        return " ".join(content.split())[:max_len]
    start = max(0, idx - 80)
    end = min(len(content), idx + len(query) + 160)
    return " ".join(content[start:end].split())[:max_len]


def _score(content: str, path: Path, query: str) -> float:
    terms = [t for t in re.split(r"\W+", query.lower()) if t]
    if not terms:
        return 0.0
    low = content.lower()
    name = path.stem.lower()
    score = 0.0
    for term in terms:
        score += low.count(term)
        if term in name:
            score += 3
    return round(score / math.sqrt(max(1, len(low) / 1000)), 3)


def search_vault(
    config: ObsidianMcpConfig,
    *,
    query: str,
    path_scope: str | None = None,
    file_types: list[str] | None = None,
    limit: int | None = None,
    include_content_snippet: bool = True,
    operator_mode: bool = False,
) -> dict[str, Any]:
    q = query.strip()
    if not q:
        raise ObsidianMcpToolError("query_required")
    root = Path(config.vault_root).expanduser().resolve()
    max_results = min(max(1, limit or 10), 50)
    results: list[dict[str, Any]] = []
    total_chars = 0

    for candidate in _iter_search_files(config, path_scope, file_types, operator_mode=operator_mode):
        ok_size, size = _check_size(config, candidate)
        if not ok_size:
            continue
        rel = candidate.resolve().relative_to(root).as_posix()
        ext = _extension(candidate) or ""
        try:
            read = read_file(config, path=rel, max_chars=config.max_result_chars, operator_mode=operator_mode)
        except ObsidianMcpToolError:
            continue
        content = str(read.get("content") or "")
        score = _score(content, candidate, q)
        if score <= 0:
            continue
        stat = candidate.stat()
        item: dict[str, Any] = {
            "path": rel,
            "file_type": ext,
            "score": score,
            "modified_at": _utc_from_timestamp(stat.st_mtime),
        }
        if include_content_snippet:
            snip = _snippet(content, q)
            total_chars += len(snip)
            if total_chars <= config.max_result_chars:
                item["snippet"] = snip
            else:
                item["snippet"] = snip[: max(0, config.max_result_chars - (total_chars - len(snip)))]
                item["truncated"] = True
        results.append(item)

    results.sort(key=lambda item: (-float(item["score"]), str(item["path"])))
    return {"query": q, "results": results[:max_results]}


# (name, category, description, input_schema_summary) — order matches the MCP
# tool registration order in mcp_app.py so the registry mirrors tools/list.
_TOOL_REGISTRY: list[tuple[str, str, str, str]] = [
    ("list_directory", "Base", "List files and directories inside the configured Obsidian vault.", "path, recursive, extensions, max_depth"),
    ("search_vault", "Base", "Search Markdown, text, PDF, and DOCX content with lexical ranking.", "query, path_scope, file_types, limit, include_content_snippet"),
    ("read_file", "Base", "Read bounded content from Markdown, text, PDF, or DOCX files.", "path, start_page, end_page, section, max_chars"),
    ("create_note", "Base", "Create a Markdown note inside the configured vault policy.", "path, content, overwrite, create_parent_dirs, expected_sha256"),
    ("patch_note", "Base", "Replace an existing Markdown note as a whole-file replacement when SHA-256 matches.", "path, content, expected_sha256"),
    ("vault_map", "Vault Intelligence", "Read-only crawl returning a folder/file inventory with optional frontmatter, tags, and links.", "root_path, recursive, max_depth, file_types, include_hidden, include_frontmatter, include_links, include_tags, max_files"),
    ("vault_summarize_note", "Vault Intelligence", "Summarize one note (md/txt/pdf/docx) with action items, decisions, and entities.", "path, max_chars, summary_style, include_action_items, include_decisions, include_entities"),
    ("vault_summarize_folder", "Vault Intelligence", "Summarize a folder/subtree into themes, per-file summaries, and aggregated actions.", "root_path, recursive, max_depth, max_files, summary_style, include_file_summaries, include_themes, include_action_items"),
    ("vault_read_eml", "Email", "Parse one .eml email (headers, body, attachments metadata) with detected projects/people/actions.", "path, include_body, include_attachments, max_body_chars, redact_email_addresses, redact_phone_numbers"),
    ("vault_email_inventory", "Email", "Inventory .eml files in a folder (metadata only unless a preview is requested).", "root_path, recursive, max_depth, max_files, include_subject, include_from, include_date, include_body_preview"),
    ("vault_parse_email", "Email", "Parse one .eml into construction/PM extraction categories (RFIs, submittals, schedule, cost, owner direction, field issues, actions, decisions).", "path, extract, max_body_chars, redact_email_addresses, redact_phone_numbers"),
    ("vault_read_frontmatter", "Metadata/Graph", "Read YAML frontmatter/properties from a note plus its body and file SHA-256.", "path"),
    ("vault_update_frontmatter", "Metadata/Graph", "Update frontmatter properties (SHA-gated, body-preserving, backup + receipt).", "path, updates, merge_tags, expected_sha256, backup_before_replace"),
    ("vault_search_by_properties", "Metadata/Graph", "Find notes by frontmatter property filters and tag any/all matching.", "root_path, filters, tags_any, tags_all, limit"),
    ("vault_dataview_query", "Metadata/Graph", "Constrained structured query over note properties (no arbitrary Dataview execution).", "root_path, where, select, limit"),
    ("vault_get_backlinks", "Metadata/Graph", "Find notes that link to a target note (wikilinks and Markdown links).", "target_path, root_path, max_results"),
    ("vault_get_unlinked_mentions", "Metadata/Graph", "Find notes that mention a title/entity but do not link to it.", "target_title, root_path, max_results, include_snippets"),
    ("vault_get_note_graph", "Metadata/Graph", "Return local graph data (nodes, edges, orphans, high-degree notes) around a note or folder.", "root_path, target_path, depth, max_nodes"),
    ("vault_create_note_from_template", "Template/Daily", "Create a note from a vault template with variable substitution and frontmatter (no code execution).", "template_path, target_path, variables, frontmatter, overwrite, create_parent_dirs"),
    ("vault_append_to_daily_note", "Template/Daily", "Append structured content to a daily note (section-aware, create-if-missing, backup + receipt).", "date, section, content, create_if_missing, template_path"),
    ("vault_move_note_plan", "File Operations", "Plan a note move with a backlink-impact preview (read-only).", "source_path, target_path, update_links"),
    ("vault_move_note_apply", "File Operations", "Apply an approved move plan_id (backup, sha-gated link rewrite, receipts, max_updates).", "plan_id, update_links, max_updates, allow_overwrite"),
    ("vault_rename_note_plan", "File Operations", "Plan a note rename with a backlink-impact preview (read-only).", "source_path, new_name, update_links"),
    ("vault_rename_note_apply", "File Operations", "Apply an approved rename plan_id (backup, sha-gated link rewrite, receipts).", "plan_id, update_links, max_updates, allow_overwrite"),
    ("vault_archive_note_plan", "File Operations", "Plan moving a note to the archive folder with a backlink-impact preview (read-only).", "source_path, update_links"),
    ("vault_archive_note_apply", "File Operations", "Apply an approved archive plan_id (backup, sha-gated link rewrite, receipts).", "plan_id, update_links, max_updates, allow_overwrite"),
    ("vault_delete_note_plan", "File Operations", "Refuses permanent deletion; returns an archive plan as the safe substitute.", "source_path, update_links"),
    ("vault_curation_plan", "Curation", "Read-only second-brain analysis that returns a durable plan_id plus proposed curation actions.", "root_path, strategy, max_depth, max_files, allowed_actions, dry_run"),
    ("vault_curation_apply", "Curation", "Apply approved actions from a server-generated curation plan_id with backups, receipts, and a max_updates cap.", "plan_id, approved_actions, require_expected_sha256, backup_before_replace, max_updates"),
]


def tool_registry() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "category": category,
            "description": description,
            "input_schema_summary": schema,
            "enabled": True,
            "last_validation_status": "not_run",
        }
        for name, category, description, schema in _TOOL_REGISTRY
    ]
