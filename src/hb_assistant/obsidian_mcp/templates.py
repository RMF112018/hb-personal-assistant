"""Template-based note creation and daily-note append tools for the Obsidian MCP server.

Both tools mutate, and both route every write through ``mutations`` (create_note / patch_note)
so they inherit the full write policy: path safety, backup-before-replace, and receipts.
Template rendering is a plain ``{{var}}`` substitution — no code execution, no Jinja.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import yaml

from . import mdutil, pathsafe
from .config import ObsidianMcpConfig
from .mutations import create_note, patch_note, sha256_file
from .tools import (
    ObsidianMcpToolError,
    _extension,
    _hidden_inspection_allowed,
    resolve_safe_path,
)

_VAR_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
# A managed-template marker identifies the seeded TEMPLATE (for idempotent re-seeding) — it is not note
# content and, being before the frontmatter, would also block frontmatter detection on instantiation.
_MANAGED_MARKER_RE = re.compile(r"\A<!--\s*hb-managed:[^>]*-->\s*\n")


def _render(template: str, variables: dict[str, Any]) -> str:
    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        return str(variables[name]) if name in variables else match.group(0)

    return _VAR_RE.sub(_sub, template)


def _merge_frontmatter(text: str, frontmatter: dict[str, Any]) -> str:
    fm, body = mdutil.split_frontmatter(text)
    merged: dict[str, Any] = {**(fm or {}), **frontmatter}
    dumped = yaml.safe_dump(merged, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n{body.lstrip(chr(10))}"


def _read_template(config: ObsidianMcpConfig, template_path: str, *, operator_mode: bool) -> str:
    resolved = resolve_safe_path(config, template_path, must_exist=True)
    if pathsafe.path_blocked(resolved.relative, include_hidden=_hidden_inspection_allowed(config, operator_mode)):
        raise ObsidianMcpToolError("protected_path_blocked")
    if not resolved.path.is_file() or (_extension(resolved.path) or "") != "md":
        raise ObsidianMcpToolError("template_not_markdown")
    return resolved.path.read_text(encoding="utf-8", errors="replace")


def create_note_from_template(
    config: ObsidianMcpConfig,
    *,
    template_path: str,
    target_path: str,
    variables: dict[str, Any] | None = None,
    frontmatter: dict[str, Any] | None = None,
    sections: dict[str, str] | None = None,
    overwrite: bool = False,
    create_parent_dirs: bool = True,
    operator_mode: bool = False,
    principal_kind: str | None = None,
) -> dict[str, Any]:
    template = _read_template(config, template_path, operator_mode=operator_mode)
    # Drop the managed-template marker so it doesn't land in the instantiated note and so any template
    # frontmatter is once again the first thing in the text (required for frontmatter merge/detection).
    template = _MANAGED_MARKER_RE.sub("", template, count=1)
    rendered = _render(template, variables or {})
    # ``sections`` fills the template's ``## Heading`` scaffold with caller content, so a template-based
    # note carries body content without free-rendering. Each heading is matched (or appended) by the same
    # helper the daily-note appender uses.
    for heading, content in (sections or {}).items():
        text = str(content or "").strip()
        if text:
            rendered = _append_to_section(rendered, str(heading), text)
    if frontmatter:
        rendered = _merge_frontmatter(rendered, frontmatter)
    result = create_note(
        config,
        path=target_path,
        content=rendered,
        overwrite=overwrite,
        create_parent_dirs=create_parent_dirs,
        caller_surface="mcp_template",
        tool_name="vault_create_note_from_template",
        principal_kind=principal_kind,
    )
    result["template_path"] = resolve_safe_path(config, template_path).relative
    return result


def _resolve_date(date: str) -> str:
    value = (date or "today").strip().lower()
    if value in {"today", ""}:
        return datetime.now(timezone.utc).date().isoformat()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date.strip()):
        return date.strip()
    raise ObsidianMcpToolError("invalid_date")


def _append_to_section(text: str, section: str | None, content: str) -> str:
    block = content.rstrip("\n")
    if section is None:
        sep = "" if text.endswith("\n") or not text else "\n"
        return f"{text}{sep}{block}\n"
    heading_re = re.compile(rf"^#{{1,6}}\s+{re.escape(section)}\s*$", re.MULTILINE)
    match = heading_re.search(text)
    if not match:
        sep = "" if text.endswith("\n") or not text else "\n"
        return f"{text}{sep}\n## {section}\n\n{block}\n"
    start = match.end()
    rest = text[start:]
    nxt = _HEADING_RE.search(rest)
    insert_at = start + (nxt.start() if nxt else len(rest))
    head = text[:insert_at].rstrip("\n")
    tail = text[insert_at:]
    return f"{head}\n{block}\n\n{tail}" if tail else f"{head}\n{block}\n"


def append_to_daily_note(
    config: ObsidianMcpConfig,
    *,
    date: str = "today",
    section: str | None = None,
    content: str,
    create_if_missing: bool = True,
    template_path: str | None = None,
    operator_mode: bool = False,
    principal_kind: str | None = None,
) -> dict[str, Any]:
    if not content or not content.strip():
        raise ObsidianMcpToolError("content_required")
    if len(content) > config.max_write_chars:
        raise ObsidianMcpToolError("content_exceeds_write_cap")
    iso = _resolve_date(date)
    folder = config.daily_notes_folder.strip("/")
    rel = f"{folder}/{iso}.md" if folder else f"{iso}.md"
    resolved = resolve_safe_path(config, rel)

    if not resolved.path.exists():
        if not create_if_missing:
            raise ObsidianMcpToolError("daily_note_missing")
        base = _read_template(config, template_path, operator_mode=operator_mode) if template_path else f"# {iso}\n"
        base = _render(base, {"date": iso}) if template_path else base
        new_content = _append_to_section(base, section, content)
        result = create_note(
            config,
            path=rel,
            content=new_content,
            overwrite=False,
            create_parent_dirs=True,
            caller_surface="mcp_daily",
            tool_name="vault_append_to_daily_note",
            principal_kind=principal_kind,
        )
    else:
        current = resolved.path.read_text(encoding="utf-8", errors="replace")
        new_content = _append_to_section(current, section, content)
        result = patch_note(
            config,
            path=rel,
            content=new_content,
            expected_sha256=sha256_file(resolved.path),
            caller_surface="mcp_daily",
            tool_name="vault_append_to_daily_note",
            principal_kind=principal_kind,
        )
    result["date"] = iso
    result["section"] = section
    return result
