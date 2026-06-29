"""Read-only .eml email tools for the Obsidian MCP server.

Parses ``.eml`` files stored in the vault using only the Python standard library
(``email.parser.BytesParser`` with ``policy.default``); HTML bodies are converted to
text with the project's stdlib-only ``_SafeTextExtractor``. Attachments are metadata-only
by default and bodies are bounded by ``max_body_chars``. Path safety (hidden/protected/
traversal) is enforced exactly as for notes. Returned content is not redacted unless the
caller explicitly opts in; bulk inventory crawls write a redacted read receipt.
"""

from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from . import extract, pathsafe
from .config import ObsidianMcpConfig
from .mutations import record_read_receipt
from .tools import (
    ObsidianMcpToolError,
    _check_size,
    _extension,
    _hidden_inspection_allowed,
    resolve_safe_path,
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})\b",
    re.IGNORECASE,
)

# Construction/PM extraction categories (deterministic; scanned over subject + body).
_CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "rfis": re.compile(r"\brfi[-\s#]?\d*\b|request for information", re.IGNORECASE),
    "submittals": re.compile(r"\bsubmittal(s)?\b|shop drawing(s)?|\bsubmit(?:ted|tal)\b", re.IGNORECASE),
    "schedule_impacts": re.compile(
        r"\b(schedule|delay(?:s|ed)?|milestone(?:s)?|critical path|completion date|resequenc\w*)\b",
        re.IGNORECASE,
    ),
    "commitments": re.compile(
        r"\b(commit(?:ment|ted|s)?|we will|agree(?:d|ment)?|purchase order|change order)\b",
        re.IGNORECASE,
    ),
    "cost_exposure": re.compile(r"\$[\d,]+(?:\.\d+)?|\b(cost(?:s)?|budget|exposure|overrun|pricing|quote)\b", re.IGNORECASE),
    "owner_direction": re.compile(r"\b(owner|directive|directed|approv(?:e|ed|al)|proceed)\b", re.IGNORECASE),
    "field_issues": re.compile(r"\b(field|punch|defect|damage|safety|inspection|weather)\b", re.IGNORECASE),
}

_DEFAULT_EXTRACT = (
    "summary",
    "action_items",
    "decisions",
    "people",
    "project_refs",
    "dates",
    *_CATEGORY_PATTERNS.keys(),
)


def _resolve_eml(config: ObsidianMcpConfig, path: str, *, operator_mode: bool) -> Any:
    resolved = resolve_safe_path(config, path, must_exist=True)
    if pathsafe.path_blocked(resolved.relative, include_hidden=_hidden_inspection_allowed(config, operator_mode)):
        raise ObsidianMcpToolError("protected_path_blocked")
    if not resolved.path.is_file():
        raise ObsidianMcpToolError("path_is_not_file")
    if (_extension(resolved.path) or "") != "eml":
        raise ObsidianMcpToolError("not_an_eml_file")
    ok_size, _size = _check_size(config, resolved.path)
    if not ok_size:
        raise ObsidianMcpToolError("file_exceeds_size_cap")
    return resolved


def _parse(path: Path) -> Any:
    with path.open("rb") as fh:
        return BytesParser(policy=policy.default).parse(fh)


def _addresses(msg: Any, header: str) -> list[str]:
    raw = msg.get_all(header, [])
    out: list[str] = []
    for name, addr in getaddresses([str(r) for r in raw]):
        label = f"{name} <{addr}>".strip() if name else addr
        if label:
            out.append(label)
    return out


def _body_text(msg: Any, max_chars: int) -> tuple[str, bool, list[str]]:
    warnings: list[str] = []
    plain: str | None = None
    html_body: str | None = None
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        try:
            content = part.get_content()
        except (LookupError, ValueError):
            continue
        if ctype == "text/plain" and plain is None:
            plain = content
        elif ctype == "text/html" and html_body is None:
            html_body = content
    if plain is not None:
        text = plain
    elif html_body is not None:
        from hb_assistant.classification.body_inspector import _SafeTextExtractor

        parser = _SafeTextExtractor()
        parser.feed(html_body)
        text = parser.get_text(max_chars)
        warnings.append("html_converted")
    else:
        return "", False, ["no_text_body"]
    truncated = len(text) > max_chars
    return text[:max_chars], truncated, warnings


def _attachments(msg: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        payload = part.get_payload(decode=True)
        out.append(
            {
                "filename": part.get_filename(),
                "content_type": part.get_content_type(),
                "size_bytes": len(payload) if payload else None,
            }
        )
    return out


def _redact(text: str, *, emails: bool, phones: bool) -> str:
    if emails:
        text = _EMAIL_RE.sub("[redacted-email]", text)
    if phones:
        text = _PHONE_RE.sub("[redacted-phone]", text)
    return text


def _people(msg: Any) -> list[str]:
    seen: list[str] = []
    for header in ("from", "to", "cc"):
        for name, addr in getaddresses([str(r) for r in msg.get_all(header, [])]):
            label = name or addr
            if label and label not in seen:
                seen.append(label)
    return seen


def _headers(msg: Any) -> dict[str, Any]:
    return {
        "subject": str(msg.get("subject") or ""),
        "from": (_addresses(msg, "from") or [None])[0],
        "to": _addresses(msg, "to"),
        "cc": _addresses(msg, "cc"),
        "date": str(msg.get("date") or ""),
    }


def read_eml(
    config: ObsidianMcpConfig,
    *,
    path: str,
    include_body: bool = True,
    include_attachments: bool = False,
    max_body_chars: int = 12000,
    redact_email_addresses: bool = False,
    redact_phone_numbers: bool = False,
    operator_mode: bool = False,
) -> dict[str, Any]:
    resolved = _resolve_eml(config, path, operator_mode=operator_mode)
    msg = _parse(resolved.path)
    warnings: list[str] = []
    body = ""
    if include_body:
        body, truncated, warnings = _body_text(msg, max_body_chars)
        if truncated:
            warnings = [*warnings, "body_truncated"]
        body = _redact(body, emails=redact_email_addresses, phones=redact_phone_numbers)
    scan = f"{msg.get('subject') or ''}\n{body}"
    payload: dict[str, Any] = {
        "path": resolved.relative,
        **_headers(msg),
        "body_preview": body,
        "attachments": _attachments(msg) if include_attachments else [],
        "detected_projects": extract.entities(scan),
        "detected_people": _people(msg),
        "detected_action_items": extract.action_items(body),
        "detected_decisions": extract.decisions(body),
        "warnings": warnings,
    }
    return payload


def email_inventory(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    recursive: bool = True,
    max_depth: int | None = 3,
    max_files: int = 500,
    include_subject: bool = True,
    include_from: bool = True,
    include_date: bool = True,
    include_body_preview: bool = False,
    operator_mode: bool = False,
    principal_kind: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")
    include_hidden = _hidden_inspection_allowed(config, operator_mode)
    if pathsafe.path_blocked(resolved.relative, include_hidden=include_hidden):
        raise ObsidianMcpToolError("protected_path_blocked")

    base_depth = len(resolved.path.relative_to(resolved.root).parts) if resolved.path != resolved.root else 0
    emails: list[dict[str, Any]] = []
    truncated = False
    for item in sorted(resolved.path.rglob("*"), key=lambda p: p.as_posix().lower()):
        if pathsafe.symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel, include_hidden=include_hidden):
            continue
        depth = len(item.resolve().relative_to(resolved.root).parts) - base_depth
        if (max_depth is not None and depth > max_depth) or item.is_dir():
            continue
        if (_extension(item) or "") != "eml":
            continue
        if len(emails) >= max_files:
            truncated = True
            break
        stat = item.stat()
        entry: dict[str, Any] = {"path": rel, "size_bytes": stat.st_size}
        if include_subject or include_from or include_date or include_body_preview:
            msg = _parse(item)
            if include_subject:
                entry["subject"] = str(msg.get("subject") or "")
            if include_from:
                entry["from"] = (_addresses(msg, "from") or [None])[0]
            if include_date:
                entry["date"] = str(msg.get("date") or "")
            if include_body_preview:
                preview, _t, _w = _body_text(msg, 240)
                entry["body_preview"] = preview
        emails.append(entry)

    receipt = record_read_receipt(
        tool_name="vault_email_inventory",
        scope=resolved.relative or "/",
        principal_kind=principal_kind,
        file_count=len(emails),
        truncated=truncated,
    )
    return {"root_path": resolved.relative, "count": len(emails), "truncated": truncated, "emails": emails, "receipt": receipt}


def parse_email(
    config: ObsidianMcpConfig,
    *,
    path: str,
    extract: list[str] | None = None,
    max_body_chars: int = 12000,
    redact_email_addresses: bool = False,
    redact_phone_numbers: bool = False,
    operator_mode: bool = False,
) -> dict[str, Any]:
    from . import extract as extract_mod  # local alias; param shadows the module name

    wanted = list(extract) if extract else list(_DEFAULT_EXTRACT)
    resolved = _resolve_eml(config, path, operator_mode=operator_mode)
    msg = _parse(resolved.path)
    body, truncated, warnings = _body_text(msg, max_body_chars)
    body = _redact(body, emails=redact_email_addresses, phones=redact_phone_numbers)
    if truncated:
        warnings = [*warnings, "body_truncated"]
    scan = f"{msg.get('subject') or ''}\n{body}"

    result: dict[str, Any] = {"path": resolved.relative, **_headers(msg), "warnings": warnings}
    if "summary" in wanted:
        result["summary"] = extract_mod.lead_summary(body, max_chars=min(2000, max_body_chars))
    if "action_items" in wanted:
        result["action_items"] = extract_mod.action_items(body)
    if "decisions" in wanted:
        result["decisions"] = extract_mod.decisions(body)
    if "people" in wanted:
        result["people"] = _people(msg)
    if "project_refs" in wanted:
        result["project_refs"] = extract_mod.entities(scan)
    if "dates" in wanted:
        result["dates"] = sorted({m.group(0) for m in _DATE_RE.finditer(scan)})
    for category, pattern in _CATEGORY_PATTERNS.items():
        if category in wanted:
            result[category] = _category_hits(scan, pattern)
    return result


def _category_hits(text: str, pattern: re.Pattern[str]) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()
    for line in (ln.strip() for ln in text.splitlines() if ln.strip()):
        if pattern.search(line) and line.lower() not in seen:
            seen.add(line.lower())
            hits.append(line)
        if len(hits) >= 15:
            break
    return hits
