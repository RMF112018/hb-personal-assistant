"""Safe maintenance for retiring pre-hygiene generated source cards.

Retires (marks ``stale``) generated cards whose SOURCE path now falls under the hard-exclusion or
deferred policy — e.g. accidental dependency-tree cards or deferred insurance-renewal PDFs from
before A1.9/A1.10. Non-destructive by default (dry-run): it never deletes source rows or source
files, and only deletes the generated ``.md`` card file when an explicit ``delete_files`` flag is
passed (resolved through the same vault write-policy guards used by the writer).
"""

from __future__ import annotations

from typing import Any

from .config import ObsidianMcpConfig
from .mutations import resolve_markdown_write_path
from .source_index_repository import SourceIndexRepository
from .source_indexer import is_deferred_source_path, is_excluded_source_path
from .tools import ObsidianMcpToolError

_SAMPLE_LIMIT = 25


def _matches_retire_policy(source_rel_path: str | None, config: ObsidianMcpConfig) -> str | None:
    """Return the matching policy ('excluded'|'deferred') for a source path, else None."""
    if not source_rel_path:
        return None
    if is_excluded_source_path(source_rel_path, config):
        return "excluded"
    if is_deferred_source_path(source_rel_path, config):
        return "deferred"
    return None


def retire_source_cards(repo: SourceIndexRepository, config: ObsidianMcpConfig, *,
                        apply: bool = False, delete_files: bool = False) -> dict[str, Any]:
    """Retire generated cards for now-excluded/deferred source classes.

    Dry-run (default ``apply=False``) mutates nothing and returns counts + sample paths. ``apply``
    marks matched generated-note rows ``stale``. ``delete_files`` (only with ``apply``) additionally
    removes the generated card ``.md`` file (never the source). Source rows/files are never touched.
    """
    rows = repo.list_generated_notes(statuses=("generated",))
    matched: list[dict[str, Any]] = []
    for row in rows:
        policy = _matches_retire_policy(row.get("source_rel_path"), config)
        if policy is not None:
            matched.append({**row, "policy": policy})

    result: dict[str, Any] = {
        "apply": bool(apply),
        "delete_files": bool(delete_files and apply),
        "matched_count": len(matched),
        "by_policy": {
            "excluded": sum(1 for m in matched if m["policy"] == "excluded"),
            "deferred": sum(1 for m in matched if m["policy"] == "deferred"),
        },
        "sample_paths": [m["note_rel_path"] for m in matched[:_SAMPLE_LIMIT]],
        "retired_count": 0,
        "files_deleted": 0,
        "files_missing": 0,
    }
    if not apply or not matched:
        return result

    retired = 0
    files_deleted = 0
    files_missing = 0
    for m in matched:
        repo.set_generated_note_status(m["generated_note_id"], "stale")
        retired += 1
        if delete_files and m.get("note_rel_path"):
            try:
                resolved = resolve_markdown_write_path(
                    config, str(m["note_rel_path"]), must_exist=True, parent_must_exist=False
                )
                resolved.path.unlink()
                files_deleted += 1
            except (ObsidianMcpToolError, OSError):
                files_missing += 1  # file already gone / not resolvable — row still retired
    result["retired_count"] = retired
    result["files_deleted"] = files_deleted
    result["files_missing"] = files_missing
    return result
