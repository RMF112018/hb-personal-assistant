"""Construction/PM domain extraction tools for the Obsidian MCP server.

All read-only and deterministic — they reuse the ``extract`` engine, the ``.eml`` parser, and
the project-detection primitives to surface action items, decisions, risks, project status,
and project mentions across notes and emails. (Optional LLM enrichment is deferred; these
stay deterministic so they are fast and fully testable.)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import extract, mdutil, pathsafe
from .config import ObsidianMcpConfig
from .eml import read_eml
from .mutations import record_read_receipt
from .tools import (
    ObsidianMcpToolError,
    _extension,
    _hidden_inspection_allowed,
    read_file,
    resolve_safe_path,
)

_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b")
_RISK_RE = re.compile(
    r"\b(risk|exposure|delay(?:s|ed)?|concern|issue|blocker|impact|critical|behind schedule|"
    r"over budget|shortfall|liquidated damages|claim|backcharge)\b",
    re.IGNORECASE,
)
_SCHEDULE_RE = re.compile(
    r"\b(schedule|milestone|completion date|critical path|resequenc\w*|float|look-?ahead|delay)\b",
    re.IGNORECASE,
)
_COST_RE = re.compile(r"\$[\d,]+(?:\.\d+)?|\b(cost|budget|exposure|overrun|change order|pricing|quote|allowance)\b", re.IGNORECASE)
_NOTE_TYPES = {"md", "txt", "pdf", "docx"}
_DEFAULT_ACTION_FIELDS = ("action_items", "decisions", "risks", "owners", "dates")
_MAX_HITS = 25


def _hits(text: str, pattern: re.Pattern[str], *, limit: int = _MAX_HITS) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in (ln.strip() for ln in text.splitlines() if ln.strip()):
        if pattern.search(line) and line.lower() not in seen:
            seen.add(line.lower())
            out.append(line.lstrip("-*> ").strip())
        if len(out) >= limit:
            break
    return out


def _dates(text: str) -> list[str]:
    return sorted({m.group(0) for m in _DATE_RE.finditer(text)})


def _open_questions(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip().endswith("?")][:_MAX_HITS]


def _read_one(config: ObsidianMcpConfig, path: str, *, source_type: str, max_chars: int, operator_mode: bool):
    """Return (rel, title, body, people) for a note or email."""
    is_email = source_type == "email" or path.lower().endswith(".eml")
    if is_email:
        email = read_eml(config, path=path, include_body=True, max_body_chars=max_chars, operator_mode=operator_mode)
        return email["path"], email.get("subject") or Path(path).stem, str(email.get("body_preview") or ""), email.get("detected_people", [])
    read = read_file(config, path=path, max_chars=max_chars, operator_mode=operator_mode)
    text = str(read.get("content") or "")
    return read["path"], mdutil.title_of(read["path"], text), text, []


def _walk(config: ObsidianMcpConfig, root_path: str, *, exts: set[str], max_files: int, operator_mode: bool, max_depth: int | None = None) -> tuple[Any, list[str], bool]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")
    include_hidden = _hidden_inspection_allowed(config, operator_mode)
    if pathsafe.path_blocked(resolved.relative, include_hidden=include_hidden):
        raise ObsidianMcpToolError("protected_path_blocked")
    base_depth = len(resolved.path.relative_to(resolved.root).parts) if resolved.path != resolved.root else 0
    rels: list[str] = []
    truncated = False
    for item in sorted(resolved.path.rglob("*"), key=lambda p: p.as_posix().lower()):
        if pathsafe.symlink_escapes(item, resolved.root) or item.is_dir():
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel, include_hidden=include_hidden):
            continue
        depth = len(item.resolve().relative_to(resolved.root).parts) - base_depth
        if (max_depth is not None and depth > max_depth) or (_extension(item) or "") not in exts:
            continue
        if len(rels) >= max_files:
            truncated = True
            break
        rels.append(rel)
    return resolved, rels, truncated


def _extract_fields(body: str, people: list[str], fields: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "action_items" in fields:
        out["action_items"] = extract.action_items(body)
    if "decisions" in fields:
        out["decisions"] = extract.decisions(body)
    if "risks" in fields:
        out["risks"] = _hits(body, _RISK_RE)
    if "owners" in fields:
        out["owners"] = people or extract.entities(body)
    if "dates" in fields:
        out["dates"] = _dates(body)
    return out


def extract_action_items(
    config: ObsidianMcpConfig,
    *,
    path: str,
    source_type: str = "note",
    extract_fields: list[str] | None = None,
    max_chars: int = 12000,
    operator_mode: bool = False,
    principal_kind: str | None = None,
) -> dict[str, Any]:
    fields = {f for f in (extract_fields or _DEFAULT_ACTION_FIELDS) if f in _DEFAULT_ACTION_FIELDS}
    if source_type == "folder":
        exts = _NOTE_TYPES | {"eml"}
        resolved, rels, truncated = _walk(config, path, exts=exts, max_files=100, operator_mode=operator_mode)
        agg: dict[str, list[str]] = {f: [] for f in fields}
        for rel in rels:
            st = "email" if rel.lower().endswith(".eml") else "note"
            _r, _t, body, people = _read_one(config, rel, source_type=st, max_chars=max_chars, operator_mode=operator_mode)
            for key, vals in _extract_fields(body, people, fields).items():
                agg[key].extend(vals)
        receipt = record_read_receipt(
            tool_name="vault_extract_action_items", scope=resolved.relative or "/",
            principal_kind=principal_kind, file_count=len(rels), truncated=truncated,
        )
        result: dict[str, Any] = {"source": resolved.relative, "source_type": "folder", "files": len(rels), "truncated": truncated, "receipt": receipt}
        for key in fields:
            result[key] = list(dict.fromkeys(agg[key]))[:_MAX_HITS]
        return result

    rel, _title, body, people = _read_one(config, path, source_type=source_type, max_chars=max_chars, operator_mode=operator_mode)
    return {"source": rel, "source_type": source_type, **_extract_fields(body, people, fields)}


def project_status_summary(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    lookback_days: int = 30,
    include: list[str] | None = None,
    max_files: int = 100,
    operator_mode: bool = False,
    principal_kind: str | None = None,
) -> dict[str, Any]:
    sections = set(include or ["actions", "risks", "schedule", "cost", "decisions", "open_questions", "summary", "status"])
    exts = _NOTE_TYPES | {"eml"}
    resolved, rels, truncated = _walk(config, root_path, exts=exts, max_files=max_files, operator_mode=operator_mode)

    summaries: list[str] = []
    statuses: list[dict[str, str]] = []
    actions: list[str] = []
    decisions: list[str] = []
    risks: list[str] = []
    schedule: list[str] = []
    cost: list[str] = []
    questions: list[str] = []
    for rel in rels:
        st = "email" if rel.lower().endswith(".eml") else "note"
        _r, title, body, _people = _read_one(config, rel, source_type=st, max_chars=4000, operator_mode=operator_mode)
        summaries.append(f"{title}: {extract.lead_summary(body, max_chars=160)}")
        actions.extend(extract.action_items(body))
        decisions.extend(extract.decisions(body))
        risks.extend(_hits(body, _RISK_RE))
        schedule.extend(_hits(body, _SCHEDULE_RE))
        cost.extend(_hits(body, _COST_RE))
        questions.extend(_open_questions(body))
        if st == "note":
            fm, _b = mdutil.split_frontmatter(body)
            if fm and fm.get("status"):
                statuses.append({"path": rel, "status": str(fm.get("status"))})

    receipt = record_read_receipt(
        tool_name="vault_project_status_summary", scope=resolved.relative or "/",
        principal_kind=principal_kind, file_count=len(rels), truncated=truncated,
    )
    payload: dict[str, Any] = {
        "root_path": resolved.relative,
        "lookback_days": lookback_days,
        "files_considered": len(rels),
        "truncated": truncated,
        "sources": rels,
        "receipt": receipt,
    }
    if "summary" in sections:
        payload["executive_summary"] = summaries[:_MAX_HITS]
    if "status" in sections:
        payload["current_status"] = statuses
    if "actions" in sections:
        payload["action_items"] = list(dict.fromkeys(actions))[:_MAX_HITS]
    if "decisions" in sections:
        payload["decisions"] = list(dict.fromkeys(decisions))[:_MAX_HITS]
    if "risks" in sections:
        payload["risks"] = list(dict.fromkeys(risks))[:_MAX_HITS]
    if "schedule" in sections:
        payload["schedule_mentions"] = list(dict.fromkeys(schedule))[:_MAX_HITS]
    if "cost" in sections:
        payload["cost_mentions"] = list(dict.fromkeys(cost))[:_MAX_HITS]
    if "open_questions" in sections:
        payload["open_questions"] = list(dict.fromkeys(questions))[:_MAX_HITS]
    return payload


def _detect_projects(text: str, aliases: list[str]) -> list[str]:
    found: list[str] = []
    try:
        from hb_assistant.construction.email.project_matcher import HB_PROJECT_NUMBER_RE
        from hb_assistant.construction.second_brain.local_ai.project_aliases import resolve_project

        found += HB_PROJECT_NUMBER_RE.findall(text)
        project = resolve_project(text)
        if project:
            found.append(project)
    except Exception:  # noqa: BLE001 - construction helpers/seed optional at runtime
        found += re.findall(r"\b\d{2}-\d{3}-\d{2}\b", text)
    for alias in aliases:
        if alias and re.search(rf"\b{re.escape(alias)}\b", text, re.IGNORECASE):
            found.append(alias)
    return sorted(dict.fromkeys(found))


def extract_project_mentions(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    project_aliases: list[str] | None = None,
    max_files: int = 200,
    include_snippets: bool = False,
    operator_mode: bool = False,
    principal_kind: str | None = None,
) -> dict[str, Any]:
    aliases = project_aliases or []
    exts = _NOTE_TYPES | {"eml"}
    resolved, rels, truncated = _walk(config, root_path, exts=exts, max_files=max_files, operator_mode=operator_mode)
    mentions: list[dict[str, Any]] = []
    for rel in rels:
        st = "email" if rel.lower().endswith(".eml") else "note"
        _r, title, body, _people = _read_one(config, rel, source_type=st, max_chars=8000, operator_mode=operator_mode)
        projects = _detect_projects(f"{title}\n{body}", aliases)
        if projects:
            entry: dict[str, Any] = {"path": rel, "projects": projects}
            if include_snippets:
                entry["snippet"] = " ".join(body.split())[:200]
            mentions.append(entry)
    receipt = record_read_receipt(
        tool_name="vault_extract_project_mentions", scope=resolved.relative or "/",
        principal_kind=principal_kind, file_count=len(rels), truncated=truncated,
    )
    return {"root_path": resolved.relative, "files_scanned": len(rels), "truncated": truncated, "mentions": mentions, "receipt": receipt}
