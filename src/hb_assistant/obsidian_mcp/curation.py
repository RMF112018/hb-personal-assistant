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

from . import plan_store
from .config import ObsidianMcpConfig
from .mutations import create_note, patch_note, sha256_file
from .tools import ObsidianMcpToolError, resolve_safe_path

# Always-blocked top-level vault segments. Every member is also dot-prefixed, so
# the generic hidden-segment rule covers them too — they are listed explicitly so
# they stay blocked even when hidden inspection is otherwise honored.
CURATION_PROTECTED_SEGMENTS = {".git", ".obsidian", ".trash", ".venv", ".smart-env", ".hb-assistant"}

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

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\s*\n?", re.DOTALL)
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9][\w/-]*)")
_WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_RELATED_RE = re.compile(r"^#{2,}\s+Related\b", re.MULTILINE | re.IGNORECASE)

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
# Path safety (always-on; never overridable by OAuth clients).
# ---------------------------------------------------------------------------
def _path_blocked(rel: str, *, include_hidden: bool) -> bool:
    for part in (p for p in rel.split("/") if p):
        if part in CURATION_PROTECTED_SEGMENTS:
            return True
        if part.startswith(".") and not include_hidden:
            return True
    return False


def _symlink_escapes(item: Path, root: Path) -> bool:
    if not item.is_symlink():
        return False
    try:
        item.resolve().relative_to(root)
    except ValueError:
        return True
    return False


# ---------------------------------------------------------------------------
# Markdown analysis helpers.
# ---------------------------------------------------------------------------
def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        loaded = None
    fm = loaded if isinstance(loaded, dict) else {}
    return fm, text[match.end():]


def _frontmatter_tags(fm: dict[str, Any] | None) -> list[str]:
    if not fm:
        return []
    raw = fm.get("tags")
    if isinstance(raw, str):
        raw = [t for t in re.split(r"[,\s]+", raw) if t]
    if not isinstance(raw, list):
        return []
    return [str(t).strip().lstrip("#") for t in raw if str(t).strip()]


def _extract_tags(body: str, fm: dict[str, Any] | None) -> list[str]:
    tags = {m.group(1) for m in _TAG_RE.finditer(body)}
    tags.update(_frontmatter_tags(fm))
    return sorted(tags)


def _normalize_tag(tag: str) -> str:
    norm = re.sub(r"[\s_]+", "-", tag.strip().lstrip("#").lower())
    norm = re.sub(r"[^a-z0-9/-]", "", norm)
    return norm.strip("-/")


def _normalized(tags: list[str]) -> list[str]:
    return sorted({n for n in (_normalize_tag(t) for t in tags) if n})


def _link_target(raw: str) -> str:
    return raw.split("|", 1)[0].split("#", 1)[0].strip()


def _extract_wikilinks(text: str) -> list[str]:
    seen: list[str] = []
    for raw in _WIKILINK_RE.findall(text):
        target = _link_target(raw)
        if target and target not in seen:
            seen.append(target)
    return seen


def _title_of(rel: str, text: str) -> str:
    match = _H1_RE.search(text)
    return match.group(1).strip() if match else Path(rel).stem


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
    if _FRONTMATTER_RE.match(text):
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
        if _symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if _path_blocked(rel, include_hidden=effective_hidden):
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
        if _symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if _path_blocked(rel, include_hidden=False):
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
