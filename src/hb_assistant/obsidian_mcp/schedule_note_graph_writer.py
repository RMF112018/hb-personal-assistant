"""Apply deterministic schedule graph links to hb-schedule-graph managed blocks (Phase 20)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from hb_assistant.obsidian_mcp.schedule_note_graph import (
    GRAPH_MANAGED_BEGIN,
    GRAPH_MANAGED_END,
)
from hb_assistant.obsidian_mcp.schedule_review_note_generator import MANAGED_END as NOTE_MANAGED_END

_GRAPH_BLOCK_RE = re.compile(
    rf"({re.escape(GRAPH_MANAGED_BEGIN)})(.*?)({re.escape(GRAPH_MANAGED_END)})",
    re.DOTALL,
)


@dataclass
class ScheduleGraphWriteResult:
    relative_path: str
    action: str
    links_written: int = 0
    conflict: bool = False
    message: str | None = None


def _reject_path_traversal(relative_path: str) -> None:
    if ".." in Path(relative_path).parts:
        raise ValueError("path_traversal_rejected")


def _graph_body_from_lines(lines: list[str]) -> str:
    cleaned = [ln.rstrip() for ln in lines if ln.strip()]
    if not cleaned:
        return "## Schedule Graph Links\n"
    return "## Schedule Graph Links\n\n" + "\n".join(cleaned) + "\n"


def upsert_schedule_graph_block(existing: str, link_lines: list[str]) -> str:
    """Insert or replace hb-schedule-graph block after hb-schedule-note:end."""
    if NOTE_MANAGED_END not in existing:
        raise ValueError("schedule_note_managed_block_missing")
    body = _graph_body_from_lines(link_lines)
    block = f"\n\n{GRAPH_MANAGED_BEGIN}\n{body}{GRAPH_MANAGED_END}\n"
    if GRAPH_MANAGED_BEGIN in existing and GRAPH_MANAGED_END in existing:
        return _GRAPH_BLOCK_RE.sub(rf"\1\n{body}\3", existing, count=1)
    insert_at = existing.index(NOTE_MANAGED_END) + len(NOTE_MANAGED_END)
    prefix = existing[:insert_at]
    suffix = existing[insert_at:]
    return prefix + block + suffix.lstrip("\n")


def extract_manual_tail(existing: str) -> str:
    """Content after hb-schedule-graph:end (operator manual notes)."""
    if GRAPH_MANAGED_END not in existing:
        return ""
    return existing.split(GRAPH_MANAGED_END, 1)[1]


def apply_schedule_graph_links(
    *,
    vault_root: Path,
    lines_by_source: dict[str, list[str]],
    dry_run: bool = True,
) -> list[ScheduleGraphWriteResult]:
    root = vault_root.resolve()
    results: list[ScheduleGraphWriteResult] = []
    for rel_path in sorted(lines_by_source):
        link_lines = lines_by_source[rel_path]
        if not link_lines:
            continue
        _reject_path_traversal(rel_path)
        target = (root / rel_path).resolve()
        if root not in target.parents:
            raise ValueError("vault_root_violation")
        if not target.exists():
            results.append(
                ScheduleGraphWriteResult(
                    relative_path=rel_path,
                    action="skipped_missing_note",
                    conflict=True,
                    message="note_not_found",
                )
            )
            continue
        existing = target.read_text(encoding="utf-8")
        manual_tail = extract_manual_tail(existing)
        updated = upsert_schedule_graph_block(existing, link_lines)
        if manual_tail and manual_tail not in updated:
            raise ValueError("manual_content_clobbered")
        if dry_run:
            action = "planned_update" if GRAPH_MANAGED_BEGIN in existing else "planned_insert"
            results.append(
                ScheduleGraphWriteResult(
                    relative_path=rel_path,
                    action=action,
                    links_written=len(link_lines),
                )
            )
            continue
        if updated == existing:
            results.append(
                ScheduleGraphWriteResult(
                    relative_path=rel_path,
                    action="unchanged",
                    links_written=len(link_lines),
                )
            )
            continue
        target.write_text(updated, encoding="utf-8")
        results.append(
            ScheduleGraphWriteResult(
                relative_path=rel_path,
                action="updated",
                links_written=len(link_lines),
            )
        )
    return results
