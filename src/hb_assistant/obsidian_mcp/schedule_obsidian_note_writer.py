"""Vault write helpers for schedule second-brain notes (Phase 19)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hb_assistant.obsidian_mcp.schedule_review_note_generator import (
    MANAGED_BEGIN,
    MANAGED_END,
    assert_note_safe,
    render_note_markdown,
)


@dataclass
class ScheduleNoteWriteResult:
    relative_path: str
    action: str
    conflict: bool = False
    message: str | None = None


def _reject_path_traversal(relative_path: str) -> None:
    if ".." in Path(relative_path).parts:
        raise ValueError("path_traversal_rejected")


def _replace_managed_block(existing: str, managed_body: str) -> str:
    pattern = re.compile(
        rf"({re.escape(MANAGED_BEGIN)})(.*?)({re.escape(MANAGED_END)})",
        re.DOTALL,
    )
    if MANAGED_BEGIN not in existing or MANAGED_END not in existing:
        raise ValueError("managed_block_missing")
    return pattern.sub(rf"\1\n{managed_body.strip()}\n\3", existing, count=1)


def apply_schedule_note_write(
    *,
    vault_root: Path,
    relative_path: str,
    payload: dict[str, Any],
    dry_run: bool = True,
    advisory_markdown: str | None = None,
) -> ScheduleNoteWriteResult:
    _reject_path_traversal(relative_path)
    target = (vault_root / relative_path).resolve()
    root = vault_root.resolve()
    if root not in target.parents and target != root:
        raise ValueError("vault_root_violation")
    markdown = render_note_markdown(payload, advisory_markdown=advisory_markdown)
    assert_note_safe(markdown)
    managed_body = markdown.split(MANAGED_BEGIN, 1)[1].split(MANAGED_END, 1)[0].strip()
    if dry_run:
        action = "planned_create" if not target.exists() else "planned_update"
        return ScheduleNoteWriteResult(relative_path=relative_path, action=action)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(markdown, encoding="utf-8")
        return ScheduleNoteWriteResult(relative_path=relative_path, action="created")
    existing = target.read_text(encoding="utf-8")
    if MANAGED_BEGIN in existing and MANAGED_END in existing:
        updated = _replace_managed_block(existing, managed_body)
        assert_note_safe(updated)
        target.write_text(updated, encoding="utf-8")
        return ScheduleNoteWriteResult(relative_path=relative_path, action="updated")
    return ScheduleNoteWriteResult(
        relative_path=relative_path,
        action="conflict",
        conflict=True,
        message="existing_note_without_managed_block",
    )
