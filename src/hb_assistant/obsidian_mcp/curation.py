"""Plan-first second-brain curation for the UI-managed Obsidian MCP server.

Three entrypoints back the ``vault_map`` / ``vault_curation_plan`` /
``vault_curation_apply`` MCP tools:

* ``vault_map`` and ``build_curation_plan`` are read-only — they crawl and
  analyze notes but never touch the vault.
* ``apply_curation_plan`` is the only mutating path. It executes *only* a
  server-generated ``plan_id`` (no crawl-and-mutate, no arbitrary write
  instructions), routing every change through the existing ``mutations.py``
  write policy (expected_sha256, backups, receipts) and capping the number of
  files touched with ``max_updates``.

Hidden/system/protected paths (``.git``, ``.obsidian``, ``.trash``, ``.venv``,
``.smart-env``, ``.hb-assistant`` and any dot-prefixed segment) are filtered
for OAuth clients and can never be overridden by them; only a local operator
(static bearer / no-auth) with the explicit ``curation_operator_hidden_inspection``
config opt-in may broaden inspection, and the hard protected set stays blocked
even then.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import mdutil, pathsafe, plan_store
from .config import ObsidianMcpConfig
from .mutations import create_note, patch_note, sha256_file
from .tools import ObsidianMcpToolError, resolve_safe_path

MUTATING_ACTIONS = {
    "add_frontmatter",
    "suggest_tags",
    "append_related_links",
    "suggest_links",
    "create_index_notes",
    "create_moc_notes",
}
DEFAULT_ALLOWED_ACTIONS = sorted(MUTATING_ACTIONS)

_OP_RANK = {"prepend_frontmatter": 0, "merge_frontmatter_tags": 1, "append_section": 2}

_RELATED_RE = re.compile(r"^#{2,}\s+Related\b", re.MULTILINE | re.IGNORECASE)

# Shared Markdown helpers live in mdutil; alias them to keep call sites terse.
_split_frontmatter = mdutil.split_frontmatter
_frontmatter_tags = mdutil.frontmatter_tags
_extract_tags = mdutil.extract_tags
_normalized = mdutil.normalized_tags
_extract_wikilinks = mdutil.extract_wikilinks
_title_of = mdutil.title_of

_PREVIEW_CHARS = 240
_MIN_TITLE_MATCH = 4
_MAX_SUGGESTED_LINKS = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).replace(microsecond=0).isoformat()


def _preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat[:_PREVIEW_CHARS]


# ---------------------------------------------------------------------------
# Markdown analysis helpers.
# ---------------------------------------------------------------------------
def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _folder_name(folder: str) -> str:
    return Path(folder).name if folder else "Vault"


def _frontmatter_block(title: str, tags: list[str]) -> str:
    payload = {"title": title, "created": _now_iso()[:10], "tags": tags}
    dumped = yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n"


def _moc_body(name: str, notes: list[str]) -> str:
    lines = [f"# {name} MOC", "", f"Map of content for **{name}**.", "", "## Notes", ""]
    lines += [f"- [[{note}]]" for note in sorted(set(notes))]
    lines.append("")
    return "\n".join(lines)


def _index_body(name: str, notes: list[str]) -> str:
    lines = [f"# {name} Index", "", "## Notes", ""]
    lines += [f"- [[{note}]]" for note in sorted(set(notes))]
    lines.append("")
    return "\n".join(lines)


def _related_block(links: list[str]) -> str:
    lines = ["", "## Related", ""]
    lines += [f"- [[{link}]]" for link in links]
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Apply-time edit operations (pure text transforms, canonical order).
# ---------------------------------------------------------------------------
def _op_prepend_frontmatter(text: str, block: str) -> str:
    if mdutil.FRONTMATTER_RE.match(text):
        return text
    return block + text


def _op_merge_tags(text: str, tags: list[str]) -> str:
    fm, body = _split_frontmatter(text)
    base = fm if fm is not None else {}
    existing = _frontmatter_tags(base)
    merged = list(dict.fromkeys([*existing, *tags]))
    new_fm = {**base, "tags": merged}
    dumped = yaml.safe_dump(new_fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n{body.lstrip(chr(10))}"


def _op_append_related(text: str, links: list[str]) -> str:
    if _RELATED_RE.search(text) or not links:
        return text
    sep = "" if text.endswith("\n") else "\n"
    return text + sep + _related_block(links)


def _combine_edits(text: str, ops: list[dict[str, Any]]) -> str:
    out = text
    for op in sorted(ops, key=lambda o: _OP_RANK.get(o["op"], 99)):
        kind = op["op"]
        if kind == "prepend_frontmatter":
            out = _op_prepend_frontmatter(out, op["payload"])
        elif kind == "merge_frontmatter_tags":
            out = _op_merge_tags(out, list(op["payload"].get("tags", [])))
        elif kind == "append_section":
            out = _op_append_related(out, list(op["payload"].get("links", [])))
    return out


# ---------------------------------------------------------------------------
# Read-only vault crawl.
# ---------------------------------------------------------------------------
def _scoped_iter(resolved: Any, *, recursive: bool) -> Any:
    return resolved.path.rglob("*") if recursive else resolved.path.iterdir()


def _base_depth(resolved: Any) -> int:
    if resolved.path == resolved.root:
        return 0
    return len(resolved.path.relative_to(resolved.root).parts)


def vault_map(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    recursive: bool = True,
    max_depth: int | None = 4,
    file_types: list[str] | None = None,
    include_hidden: bool = False,
    include_frontmatter: bool = True,
    include_links: bool = True,
    include_tags: bool = True,
    max_files: int = 500,
    operator_mode: bool = False,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")

    effective_hidden = bool(include_hidden and operator_mode and config.curation_operator_hidden_inspection)
    exts = {e.lower().lstrip(".") for e in (file_types or ["md"])}
    base_depth = _base_depth(resolved)
    files: list[dict[str, Any]] = []
    folders: dict[str, int] = {}
    truncated = False

    for item in sorted(_scoped_iter(resolved, recursive=recursive), key=lambda p: p.as_posix().lower()):
        if pathsafe.symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel, include_hidden=effective_hidden):
            continue
        depth = len(item.resolve().relative_to(resolved.root).parts) - base_depth
        if max_depth is not None and depth > max_depth:
            continue
        if item.is_dir():
            folders.setdefault(rel, 0)
            continue
        ext = item.suffix.lower().lstrip(".") or None
        if exts and (ext or "") not in exts:
            continue
        if len(files) >= max_files:
            truncated = True
            break
        stat = item.stat()
        entry: dict[str, Any] = {
            "path": rel,
            "name": item.name,
            "extension": ext,
            "size_bytes": stat.st_size,
            "modified_at": _utc(stat.st_mtime),
        }
        if ext == "md" and (include_frontmatter or include_tags or include_links):
            text = _read_text(item)
            fm, body = _split_frontmatter(text)
            if include_frontmatter:
                entry["has_frontmatter"] = fm is not None
            if include_tags:
                entry["tags"] = _normalized(_extract_tags(body, fm))
            if include_links:
                entry["links"] = _extract_wikilinks(text)
        files.append(entry)
        parent = Path(rel).parent
        folder = parent.as_posix() if parent != Path(".") else ""
        folders[folder] = folders.get(folder, 0) + 1

    folder_list = [{"path": k, "note_count": v} for k, v in sorted(folders.items())]
    return {
        "root": str(resolved.root),
        "path": resolved.relative,
        "folders": folder_list,
        "files": files,
        "truncated": truncated,
    }


def _scan_notes(
    config: ObsidianMcpConfig,
    root_path: str,
    *,
    max_depth: int | None,
    max_files: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")
    base_depth = _base_depth(resolved)
    notes: list[dict[str, Any]] = []
    folders: dict[str, dict[str, Any]] = {}

    for item in sorted(resolved.path.rglob("*"), key=lambda p: p.as_posix().lower()):
        if pathsafe.symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel, include_hidden=False):
            continue
        depth = len(item.resolve().relative_to(resolved.root).parts) - base_depth
        if max_depth is not None and depth > max_depth:
            continue
        if item.is_dir() or item.suffix.lower() != ".md":
            continue
        if len(notes) >= max_files:
            break
        text = _read_text(item)
        fm, body = _split_frontmatter(text)
        title = _title_of(rel, text)
        note = {
            "rel": rel,
            "sha": sha256_file(item),
            "title": title,
            "has_frontmatter": fm is not None,
            "normalized_tags": _normalized(_extract_tags(body, fm)),
            "frontmatter_tags_norm": _normalized(_frontmatter_tags(fm)),
            "wikilinks": _extract_wikilinks(text),
            "has_related_section": bool(_RELATED_RE.search(body)),
            "body_lower": body.lower(),
        }
        notes.append(note)
        parent = Path(rel).parent
        folder = parent.as_posix() if parent != Path(".") else ""
        info = folders.setdefault(folder, {"note_count": 0, "has_index": False, "notes": []})
        info["note_count"] += 1
        info["notes"].append(title)
        stem = Path(rel).stem.lower()
        if "moc" in stem or stem in {"index", "_index", "readme"}:
            info["has_index"] = True
    return notes, folders


# ---------------------------------------------------------------------------
# Plan construction (read-only w.r.t. the vault).
# ---------------------------------------------------------------------------
def build_curation_plan(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    strategy: str = "second_brain",
    max_depth: int | None = 5,
    max_files: int = 300,
    allowed_actions: list[str] | None = None,
    dry_run: bool = True,
    operator_mode: bool = False,
) -> dict[str, Any]:
    allowed = {a for a in (allowed_actions or DEFAULT_ALLOWED_ACTIONS) if a in MUTATING_ACTIONS}
    notes, folders = _scan_notes(config, root_path, max_depth=max_depth, max_files=max_files)

    actions: list[dict[str, Any]] = []
    baseline: dict[str, str] = {}
    counter = 0

    def _add(action: str, target: str, op: str, sha: str | None, preview: str, payload: Any) -> None:
        nonlocal counter
        counter += 1
        actions.append(
            {
                "id": f"a{counter:04d}",
                "action": action,
                "target_path": target,
                "op": op,
                "expected_sha256": sha,
                "preview": preview,
                "payload": payload,
            }
        )

    title_index = {n["title"].lower(): n for n in notes if n["title"]}

    for note in notes:
        baseline[note["rel"]] = note["sha"]
        if "add_frontmatter" in allowed and not note["has_frontmatter"]:
            block = _frontmatter_block(note["title"], note["normalized_tags"])
            _add("add_frontmatter", note["rel"], "prepend_frontmatter", note["sha"], _preview(block), block)
        if "suggest_tags" in allowed:
            missing = [t for t in note["normalized_tags"] if t not in note["frontmatter_tags_norm"]]
            if missing:
                _add(
                    "suggest_tags",
                    note["rel"],
                    "merge_frontmatter_tags",
                    note["sha"],
                    _preview("tags: " + ", ".join(missing)),
                    {"tags": missing},
                )
        if "append_related_links" in allowed and note["wikilinks"] and not note["has_related_section"]:
            links = note["wikilinks"][:_MAX_SUGGESTED_LINKS]
            _add(
                "append_related_links",
                note["rel"],
                "append_section",
                note["sha"],
                _preview("Related: " + ", ".join(links)),
                {"links": links},
            )

    if "suggest_links" in allowed:
        for note in notes:
            candidates: list[str] = []
            for title_l, other in title_index.items():
                if other["rel"] == note["rel"] or len(title_l) < _MIN_TITLE_MATCH:
                    continue
                if title_l in note["body_lower"] and other["title"] not in note["wikilinks"]:
                    candidates.append(other["title"])
            candidates = sorted(set(candidates))[:_MAX_SUGGESTED_LINKS]
            if candidates:
                _add(
                    "suggest_links",
                    note["rel"],
                    "append_section",
                    note["sha"],
                    _preview("Suggested links: " + ", ".join(candidates)),
                    {"links": candidates},
                )

    threshold = config.curation_dense_folder_threshold
    for folder, info in sorted(folders.items()):
        if info["note_count"] < threshold or info["has_index"]:
            continue
        name = _folder_name(folder)
        prefix = f"{folder}/" if folder else ""
        if "create_moc_notes" in allowed:
            body = _moc_body(name, info["notes"])
            _add("create_moc_notes", f"{prefix}{name} MOC.md", "create", None, _preview(body), body)
        if "create_index_notes" in allowed:
            body = _index_body(name, info["notes"])
            _add("create_index_notes", f"{prefix}_index.md", "create", None, _preview(body), body)

    counts: dict[str, int] = {}
    for action in actions:
        counts[action["action"]] = counts.get(action["action"], 0) + 1

    plan_id = plan_store.new_plan_id()
    record = {
        "plan_id": plan_id,
        "created_at": _now_iso(),
        "root_path": resolve_safe_path(config, root_path, must_exist=True).relative,
        "strategy": strategy,
        "dry_run": dry_run,
        "allowed_actions": sorted(allowed),
        "baseline_shas": baseline,
        "actions": actions,
    }
    plan_store.save_plan(record)

    return {
        "plan_id": plan_id,
        "root_path": record["root_path"],
        "strategy": strategy,
        "allowed_actions": sorted(allowed),
        "actions": [_redact_action(a) for a in actions],
        "counts": counts,
        "notes_scanned": len(notes),
    }


def _redact_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": action["id"],
        "action": action["action"],
        "target_path": action["target_path"],
        "op": action["op"],
        "expected_sha256": action["expected_sha256"],
        "preview": action["preview"],
    }


# ---------------------------------------------------------------------------
# Focused planners — emit curation-compatible plans applied via apply_curation_plan.
# ---------------------------------------------------------------------------
def _save_focused_plan(
    *, root_rel: str, strategy: str, allowed: set[str], actions: list[dict[str, Any]], baseline: dict[str, str]
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for action in actions:
        counts[action["action"]] = counts.get(action["action"], 0) + 1
    plan_id = plan_store.new_plan_id()
    plan_store.save_plan(
        {
            "plan_id": plan_id,
            "created_at": _now_iso(),
            "root_path": root_rel,
            "strategy": strategy,
            "dry_run": True,
            "allowed_actions": sorted(allowed),
            "baseline_shas": baseline,
            "actions": actions,
        }
    )
    return {
        "plan_id": plan_id,
        "root_path": root_rel,
        "strategy": strategy,
        "allowed_actions": sorted(allowed),
        "actions": [_redact_action(a) for a in actions],
        "counts": counts,
    }


def _moc_body_sections(name: str, titles: list[str], sections: list[str] | None) -> str:
    lines = [f"# {name} MOC", "", f"Map of content for **{name}**.", ""]
    for section in sections or ["notes"]:
        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append("")
        if section.lower() in {"notes", "related_notes", "overview"}:
            lines += [f"- [[{title}]]" for title in sorted(set(titles))]
        lines.append("")
    return "\n".join(lines)


def build_moc_plan(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    moc_title: str | None = None,
    target_path: str | None = None,
    max_files: int = 100,
    include_sections: list[str] | None = None,
    operator_mode: bool = False,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    notes, _folders = _scan_notes(config, root_path, max_depth=None, max_files=max_files)
    name = (moc_title or _folder_name(resolved.relative)).strip()
    prefix = f"{resolved.relative}/" if resolved.relative else ""
    target = target_path or f"{prefix}{name} MOC.md"
    body = _moc_body_sections(name, [n["title"] for n in notes], include_sections)
    action = {
        "id": "a0001",
        "action": "create_moc_notes",
        "target_path": target,
        "op": "create",
        "expected_sha256": None,
        "preview": _preview(body),
        "payload": body,
    }
    return _save_focused_plan(
        root_rel=resolved.relative, strategy="moc", allowed={"create_moc_notes"}, actions=[action], baseline={}
    )


def build_auto_link_plan(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    max_files: int = 200,
    min_confidence: float = 0.75,
    max_suggestions: int = 100,
    operator_mode: bool = False,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    notes, _folders = _scan_notes(config, root_path, max_depth=None, max_files=max_files)
    title_index = {n["title"].lower(): n for n in notes if n["title"]}
    actions: list[dict[str, Any]] = []
    baseline: dict[str, str] = {}
    counter = 0
    for note in notes:
        candidates: list[str] = []
        for title_l, other in title_index.items():
            if other["rel"] == note["rel"] or len(title_l) < _MIN_TITLE_MATCH:
                continue
            confidence = min(1.0, 0.5 + len(title_l) / 20)
            if title_l in note["body_lower"] and other["title"] not in note["wikilinks"] and confidence >= min_confidence:
                candidates.append(other["title"])
        candidates = sorted(set(candidates))[:_MAX_SUGGESTED_LINKS]
        if candidates:
            counter += 1
            baseline[note["rel"]] = note["sha"]
            actions.append(
                {
                    "id": f"a{counter:04d}",
                    "action": "suggest_links",
                    "target_path": note["rel"],
                    "op": "append_section",
                    "expected_sha256": note["sha"],
                    "preview": _preview("Suggested links: " + ", ".join(candidates)),
                    "payload": {"links": candidates},
                }
            )
            if counter >= max_suggestions:
                break
    return _save_focused_plan(
        root_rel=resolved.relative, strategy="auto_link", allowed={"suggest_links"}, actions=actions, baseline=baseline
    )


def build_bulk_tagging_plan(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    tag_namespace: str | None = None,
    max_files: int = 200,
    max_suggestions: int = 100,
    operator_mode: bool = False,
) -> dict[str, Any]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    notes, _folders = _scan_notes(config, root_path, max_depth=None, max_files=max_files)
    namespace = mdutil.normalize_tag(tag_namespace) if tag_namespace else None
    actions: list[dict[str, Any]] = []
    baseline: dict[str, str] = {}
    counter = 0
    for note in notes:
        missing = [t for t in note["normalized_tags"] if t not in note["frontmatter_tags_norm"]]
        if namespace and namespace not in note["frontmatter_tags_norm"] and namespace not in missing:
            missing.append(namespace)
        if missing:
            counter += 1
            baseline[note["rel"]] = note["sha"]
            actions.append(
                {
                    "id": f"a{counter:04d}",
                    "action": "suggest_tags",
                    "target_path": note["rel"],
                    "op": "merge_frontmatter_tags",
                    "expected_sha256": note["sha"],
                    "preview": _preview("tags: " + ", ".join(missing)),
                    "payload": {"tags": missing},
                }
            )
            if counter >= max_suggestions:
                break
    return _save_focused_plan(
        root_rel=resolved.relative, strategy="bulk_tagging", allowed={"suggest_tags"}, actions=actions, baseline=baseline
    )


def _email_note_body(email: dict[str, Any], *, link_projects: bool, include_actions: bool, include_decisions: bool) -> str:
    fm: dict[str, Any] = {"type": "email-note", "source_email": email["path"]}
    if email.get("from"):
        fm["from"] = email["from"]
    if email.get("date"):
        fm["date"] = email["date"]
    if link_projects and email.get("detected_projects"):
        fm["projects"] = email["detected_projects"]
    dumped = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    subject = email.get("subject") or Path(email["path"]).stem
    lines = [f"---\n{dumped}\n---", "", f"# {subject}", "", "## Summary", "", (email.get("body_preview") or "(no body)")[:1200], ""]
    if include_actions and email.get("detected_action_items"):
        lines += ["## Action Items", "", *[f"- [ ] {a}" for a in email["detected_action_items"]], ""]
    if include_decisions and email.get("detected_decisions"):
        lines += ["## Decisions", "", *[f"- {d}" for d in email["detected_decisions"]], ""]
    if link_projects and email.get("detected_projects"):
        lines += ["## Related", "", *[f"- [[{p}]]" for p in email["detected_projects"]], ""]
    lines += [f"> Source email: {email['path']}", ""]
    return "\n".join(lines)


def build_email_to_note_plan(
    config: ObsidianMcpConfig,
    *,
    email_path: str,
    target_folder: str,
    template_path: str | None = None,
    link_projects: bool = True,
    extract_action_items: bool = True,
    extract_decisions: bool = True,
    redact: bool = False,
    max_chars: int = 12000,
    operator_mode: bool = False,
) -> dict[str, Any]:
    from .eml import read_eml

    email = read_eml(
        config,
        path=email_path,
        include_body=True,
        max_body_chars=max_chars,
        redact_email_addresses=redact,
        redact_phone_numbers=redact,
        operator_mode=operator_mode,
    )
    folder = target_folder.strip("/")
    target = f"{folder}/{Path(email['path']).stem}.md" if folder else f"{Path(email['path']).stem}.md"
    body = _email_note_body(
        email, link_projects=link_projects, include_actions=extract_action_items, include_decisions=extract_decisions
    )
    action = {
        "id": "a0001",
        "action": "email_to_note",
        "target_path": target,
        "op": "create",
        "expected_sha256": None,
        "preview": _preview(body),
        "payload": body,
    }
    result = _save_focused_plan(
        root_rel=folder, strategy="email_to_note", allowed={"email_to_note"}, actions=[action], baseline={}
    )
    result["target_path"] = target
    result["source_email"] = email["path"]
    return result


def apply_email_to_note_plan(
    config: ObsidianMcpConfig,
    *,
    plan_id: str,
    max_updates: int = 25,
    operator_mode: bool = False,
) -> dict[str, Any]:
    return apply_curation_plan(
        config,
        plan_id=plan_id,
        approved_actions=["email_to_note"],
        max_updates=max_updates,
        operator_mode=operator_mode,
    )


# ---------------------------------------------------------------------------
# Apply (the only mutating path; executes a stored plan only).
# ---------------------------------------------------------------------------
def apply_curation_plan(
    config: ObsidianMcpConfig,
    *,
    plan_id: str,
    approved_actions: list[str] | None = None,
    require_expected_sha256: bool = True,
    backup_before_replace: bool = True,
    max_updates: int = 25,
    operator_mode: bool = False,
) -> dict[str, Any]:
    plan = plan_store.load_plan(plan_id)
    if plan is None:
        raise ObsidianMcpToolError("unknown_plan")

    allowed = set(plan.get("allowed_actions", []))
    approved = set(approved_actions or [])
    if approved - allowed:
        raise ObsidianMcpToolError("action_not_in_plan")

    baseline = plan.get("baseline_shas", {})
    selected = [a for a in plan.get("actions", []) if a.get("action") in approved]
    creates = [a for a in selected if a["op"] == "create"]
    edit_groups: dict[str, list[dict[str, Any]]] = {}
    for action in selected:
        if action["op"] != "create":
            edit_groups.setdefault(action["target_path"], []).append(action)

    units: list[tuple[str, str, list[dict[str, Any]]]] = []
    units += [("create", a["target_path"], [a]) for a in creates]
    units += [("edit", target, ops) for target, ops in edit_groups.items()]
    units.sort(key=lambda u: (u[1], u[0]))

    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    used = 0

    for kind, target, ops in units:
        labels = sorted({op["action"] for op in ops})
        if used >= max_updates:
            skipped.append({"target_path": target, "reason": "max_updates", "actions": labels})
            continue
        try:
            if kind == "create":
                result = create_note(
                    config,
                    path=target,
                    content=ops[0]["payload"],
                    overwrite=False,
                    caller_surface="mcp_curation",
                )
                applied.append(
                    {
                        "target_path": target,
                        "actions": labels,
                        "op": "create",
                        "sha256": result["sha256"],
                        "backup_path": result.get("backup_path"),
                    }
                )
            else:
                resolved = resolve_safe_path(config, target, must_exist=True)
                live_sha = sha256_file(resolved.path)
                if require_expected_sha256 and baseline.get(target) != live_sha:
                    failed.append({"target_path": target, "reason": "sha256_mismatch", "actions": labels})
                    continue
                text = _read_text(resolved.path)
                new_text = _combine_edits(text, ops)
                if new_text == text:
                    skipped.append({"target_path": target, "reason": "no_change", "actions": labels})
                    continue
                result = patch_note(
                    config,
                    path=target,
                    content=new_text,
                    expected_sha256=live_sha,
                    caller_surface="mcp_curation",
                )
                applied.append(
                    {
                        "target_path": target,
                        "actions": labels,
                        "op": "edit",
                        "sha256": result["sha256"],
                        "old_sha256": result["old_sha256"],
                        "backup_path": result.get("backup_path"),
                    }
                )
            used += 1
        except ObsidianMcpToolError as exc:
            failed.append({"target_path": target, "reason": exc.code, "actions": labels})

    counts = {"applied": len(applied), "skipped": len(skipped), "failed": len(failed)}
    receipt = {
        "plan_id": plan_id,
        "applied_at": _now_iso(),
        "approved_actions": sorted(approved),
        "max_updates": max_updates,
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "counts": counts,
    }
    plan_store.write_receipt(plan_id, receipt)
    return {
        "plan_id": plan_id,
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "counts": counts,
    }
