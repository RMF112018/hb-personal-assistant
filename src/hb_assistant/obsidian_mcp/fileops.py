"""Plan-first safe file operations (move / rename / archive) for the Obsidian MCP server.

Every operation is plan-first: a read-only ``*_plan`` tool previews the move and every
backlink that would be rewritten and persists a durable ``plan_id``; a ``*_apply`` tool
executes *only* that stored plan. Apply is sha-gated on the source and on every backlink
file, backs up the source before removing it, rewrites approved backlinks as individual
``patch_note`` writes under ``max_updates``, and receipts everything.

There is **no permanent delete**: ``delete_note_plan`` returns an *archive* plan as the safe
substitute, applied via ``vault_archive_note_apply``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import mdutil, pathsafe, plan_store
from .config import ObsidianMcpConfig
from .mutations import (
    _backup_existing,
    _event,
    create_note,
    patch_note,
    record_mutation,
    sha256_file,
)
from .tools import (
    ObsidianMcpToolError,
    _extension,
    _hidden_inspection_allowed,
    resolve_safe_path,
)

_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_PREVIEW_LIMIT = 50


def _norm(token: str) -> str:
    target = token.split("|", 1)[0].split("#", 1)[0].strip()
    if target.lower().endswith(".md"):
        target = target[:-3]
    return target.lower()


def _aliases(rel: str, title: str) -> set[str]:
    stem = Path(rel).stem
    no_md = rel[:-3] if rel.lower().endswith(".md") else rel
    return {stem.lower(), title.lower(), rel.lower(), no_md.lower()}


def _matches_source(token: str, source_aliases: set[str], source_stem: str) -> bool:
    norm = _norm(token)
    # Match the full vault-relative path/title, or — as Obsidian resolves links by
    # note name — the link's basename stem (handles relative paths like ../Inbox/Note.md).
    return norm in source_aliases or Path(norm).name == source_stem


def _rewrite_links(text: str, source_aliases: set[str], source_stem: str, new_stem: str) -> tuple[str, int]:
    count = 0

    def _wl(match: re.Match[str]) -> str:
        nonlocal count
        inner = match.group(1)
        target = inner.split("|", 1)[0].split("#", 1)[0].strip()
        suffix = inner[len(target):]
        if _matches_source(target, source_aliases, source_stem):
            count += 1
            return f"[[{new_stem}{suffix}]]"
        return match.group(0)

    def _ml(match: re.Match[str]) -> str:
        nonlocal count
        label, link = match.group(1), match.group(2)
        base = link.split("#", 1)[0]
        anchor = link[len(base):]
        if base.lower().startswith(("http://", "https://")):
            return match.group(0)
        if _matches_source(base, source_aliases, source_stem):
            count += 1
            return f"[{label}]({new_stem}.md{anchor})"
        return match.group(0)

    text = mdutil.WIKILINK_RE.sub(_wl, text)
    text = _MD_LINK_RE.sub(_ml, text)
    return text, count


def _resolve_source(config: ObsidianMcpConfig, path: str, *, operator_mode: bool) -> Any:
    resolved = resolve_safe_path(config, path, must_exist=True)
    if pathsafe.path_blocked(resolved.relative, include_hidden=_hidden_inspection_allowed(config, operator_mode)):
        raise ObsidianMcpToolError("protected_path_blocked")
    if not resolved.path.is_file() or (_extension(resolved.path) or "") != "md":
        raise ObsidianMcpToolError("markdown_only")
    return resolved


def _validate_target(config: ObsidianMcpConfig, target_path: str) -> str:
    resolved = resolve_safe_path(config, target_path, must_exist=False)
    if not resolved.relative:
        raise ObsidianMcpToolError("target_required")
    if (Path(resolved.relative).suffix.lower().lstrip(".")) != "md":
        raise ObsidianMcpToolError("markdown_only")
    if pathsafe.path_blocked(resolved.relative, include_hidden=False):
        raise ObsidianMcpToolError("protected_path_blocked")
    return resolved.relative


def _build_plan(
    config: ObsidianMcpConfig,
    *,
    op: str,
    source_path: str,
    target_path: str,
    update_links: bool,
    operator_mode: bool,
) -> dict[str, Any]:
    src = _resolve_source(config, source_path, operator_mode=operator_mode)
    target_rel = _validate_target(config, target_path)
    if target_rel == src.relative:
        raise ObsidianMcpToolError("target_equals_source")

    src_text = src.path.read_text(encoding="utf-8", errors="replace")
    source_aliases = _aliases(src.relative, mdutil.title_of(src.relative, src_text))
    source_stem = Path(src.relative).stem.lower()
    new_stem = Path(target_rel).stem
    baseline: dict[str, str] = {src.relative: sha256_file(src.path)}
    link_edits: list[dict[str, Any]] = []

    if update_links:
        root = src.root
        for item in sorted(root.rglob("*"), key=lambda p: p.as_posix().lower()):
            if pathsafe.symlink_escapes(item, root) or item.is_dir():
                continue
            rel = item.resolve().relative_to(root).as_posix()
            if rel == src.relative or pathsafe.path_blocked(rel, include_hidden=False):
                continue
            if (_extension(item) or "") != "md":
                continue
            _new, count = _rewrite_links(
                item.read_text(encoding="utf-8", errors="replace"), source_aliases, source_stem, new_stem
            )
            if count:
                link_edits.append({"path": rel, "link_count": count})
                baseline[rel] = sha256_file(item)

    plan_id = plan_store.new_plan_id("fileop")
    record = {
        "plan_id": plan_id,
        "plan_type": "file_op",
        "op": op,
        "source_path": src.relative,
        "target_path": target_rel,
        "update_links": update_links,
        "new_stem": new_stem,
        "source_aliases": sorted(source_aliases),
        "baseline_shas": baseline,
        "link_edits": link_edits,
    }
    plan_store.save_plan(record)
    return {
        "plan_id": plan_id,
        "op": op,
        "source_path": src.relative,
        "target_path": target_rel,
        "update_links": update_links,
        "backlinks_to_update": len(link_edits),
        "affected_notes": [e["path"] for e in link_edits[:_PREVIEW_LIMIT]],
        "target_exists": resolve_safe_path(config, target_rel, must_exist=False).path.exists(),
    }


def _apply_plan(
    config: ObsidianMcpConfig,
    *,
    plan_id: str,
    expected_op: str,
    update_links: bool,
    max_updates: int,
    allow_overwrite: bool,
    operator_mode: bool,
    principal_kind: str | None,
) -> dict[str, Any]:
    plan = plan_store.load_plan(plan_id)
    if plan is None or plan.get("plan_type") != "file_op":
        raise ObsidianMcpToolError("unknown_plan")
    if plan.get("op") != expected_op:
        raise ObsidianMcpToolError("plan_op_mismatch")

    src_rel = str(plan["source_path"])
    target_rel = str(plan["target_path"])
    baseline = plan.get("baseline_shas", {})
    src = resolve_safe_path(config, src_rel, must_exist=True)
    if sha256_file(src.path) != baseline.get(src_rel):
        raise ObsidianMcpToolError("sha256_mismatch")
    tgt = resolve_safe_path(config, target_rel, must_exist=False)
    if tgt.path.exists() and not allow_overwrite:
        raise ObsidianMcpToolError("target_exists")

    src_content = src.path.read_text(encoding="utf-8", errors="replace")
    tool = f"vault_{expected_op}_note_apply"
    create_note(
        config,
        path=target_rel,
        content=src_content,
        overwrite=allow_overwrite,
        create_parent_dirs=True,
        expected_sha256=sha256_file(tgt.path) if (tgt.path.exists() and allow_overwrite) else None,
        caller_surface="mcp_fileops",
        tool_name=tool,
        principal_kind=principal_kind,
        plan_id=plan_id,
    )
    _remove_source(config, src, tool_name=tool, principal_kind=principal_kind, plan_id=plan_id)

    applied_links: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    if update_links and plan.get("update_links"):
        source_aliases = set(plan.get("source_aliases", []))
        source_stem = Path(src_rel).stem.lower()
        new_stem = str(plan["new_stem"])
        used = 0
        for edit in plan.get("link_edits", []):
            path = str(edit["path"])
            if used >= max_updates:
                skipped.append({"path": path, "reason": "max_updates"})
                continue
            try:
                link_resolved = resolve_safe_path(config, path, must_exist=True)
                live_sha = sha256_file(link_resolved.path)
                if live_sha != baseline.get(path):
                    failed.append({"path": path, "reason": "sha256_mismatch"})
                    continue
                text = link_resolved.path.read_text(encoding="utf-8", errors="replace")
                new_text, count = _rewrite_links(text, source_aliases, source_stem, new_stem)
                if count == 0 or new_text == text:
                    skipped.append({"path": path, "reason": "no_change"})
                    continue
                patch_note(
                    config,
                    path=path,
                    content=new_text,
                    expected_sha256=live_sha,
                    caller_surface="mcp_fileops",
                    tool_name=tool,
                    principal_kind=principal_kind,
                    plan_id=plan_id,
                )
                applied_links.append({"path": path, "links_rewritten": count})
                used += 1
            except ObsidianMcpToolError as exc:
                failed.append({"path": path, "reason": exc.code})

    counts = {"links_updated": len(applied_links), "skipped": len(skipped), "failed": len(failed)}
    receipt = {
        "plan_id": plan_id,
        "op": expected_op,
        "moved": {"source": src_rel, "target": target_rel},
        "links_updated": applied_links,
        "skipped": skipped,
        "failed": failed,
        "counts": counts,
    }
    plan_store.write_receipt(plan_id, receipt)
    return receipt


def _remove_source(config: ObsidianMcpConfig, resolved: Any, *, tool_name: str, principal_kind: str | None, plan_id: str) -> None:
    old_sha = sha256_file(resolved.path)
    backup = _backup_existing(resolved.path, resolved.relative) if config.backup_before_replace else None
    resolved.path.unlink()
    record_mutation(
        _event(
            action="note_moved_out",
            relative_path=resolved.relative,
            status="applied",
            caller_surface="mcp_fileops",
            old_sha256=old_sha,
            backup_path=backup,
            tool_name=tool_name,
            principal_kind=principal_kind,
            plan_id=plan_id,
        )
    )


def _archive_target(config: ObsidianMcpConfig, source_rel: str) -> str:
    folder = config.archive_folder.strip("/")
    return f"{folder}/{source_rel}" if folder else source_rel


# ---------------------------------------------------------------------------
# Public plan tools (read-only).
# ---------------------------------------------------------------------------
def move_note_plan(config, *, source_path, target_path, update_links=True, operator_mode=False):
    return _build_plan(config, op="move", source_path=source_path, target_path=target_path, update_links=update_links, operator_mode=operator_mode)


def rename_note_plan(config, *, source_path, new_name, update_links=True, operator_mode=False):
    src = _resolve_source(config, source_path, operator_mode=operator_mode)
    name = new_name if new_name.lower().endswith(".md") else f"{new_name}.md"
    parent = Path(src.relative).parent
    target = (parent / name).as_posix() if str(parent) != "." else name
    return _build_plan(config, op="rename", source_path=source_path, target_path=target, update_links=update_links, operator_mode=operator_mode)


def archive_note_plan(config, *, source_path, update_links=True, operator_mode=False):
    src = _resolve_source(config, source_path, operator_mode=operator_mode)
    return _build_plan(config, op="archive", source_path=source_path, target_path=_archive_target(config, src.relative), update_links=update_links, operator_mode=operator_mode)


def delete_note_plan(config, *, source_path, update_links=True, operator_mode=False):
    plan = archive_note_plan(config, source_path=source_path, update_links=update_links, operator_mode=operator_mode)
    plan["requested_operation"] = "delete"
    plan["substituted_with"] = "archive"
    plan["note"] = "Permanent deletion is not supported. Apply with vault_archive_note_apply to archive instead."
    return plan


# ---------------------------------------------------------------------------
# Public apply tools (write; execute a stored plan only).
# ---------------------------------------------------------------------------
def move_note_apply(config, *, plan_id, update_links=True, max_updates=25, allow_overwrite=False, operator_mode=False, principal_kind=None):
    return _apply_plan(config, plan_id=plan_id, expected_op="move", update_links=update_links, max_updates=max_updates, allow_overwrite=allow_overwrite, operator_mode=operator_mode, principal_kind=principal_kind)


def rename_note_apply(config, *, plan_id, update_links=True, max_updates=25, allow_overwrite=False, operator_mode=False, principal_kind=None):
    return _apply_plan(config, plan_id=plan_id, expected_op="rename", update_links=update_links, max_updates=max_updates, allow_overwrite=allow_overwrite, operator_mode=operator_mode, principal_kind=principal_kind)


def archive_note_apply(config, *, plan_id, update_links=True, max_updates=25, allow_overwrite=False, operator_mode=False, principal_kind=None):
    return _apply_plan(config, plan_id=plan_id, expected_op="archive", update_links=update_links, max_updates=max_updates, allow_overwrite=allow_overwrite, operator_mode=operator_mode, principal_kind=principal_kind)
