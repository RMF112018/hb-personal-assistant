"""Deterministic Obsidian source cards.

A source card is a curated note that *describes and links back to* an indexed source — NOT a
copy of it. No model output (Ollama is a later slice). No raw file dumping (only a small,
bounded, labeled preview of already-indexed text, withheld for sensitive sources). No raw email
body (link sources have no extracted text by construction). Cards are written through the
existing ``create_note`` guardrails: write policy, SHA-gated overwrite, atomic write, backup,
receipt, and pathsafe protected/hidden/symlink checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ObsidianMcpConfig
from .mutations import create_note, resolve_markdown_write_path, sha256_file
from .source_index_repository import SourceIndexRepository
from .tools import ObsidianMcpToolError


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _card_rel_path(config: ObsidianMcpConfig, detail: dict[str, Any]) -> str:
    folder = (config.source_notes_folder or "Source Notes").strip("/")
    if detail.get("rel_path"):
        return f"{folder}/{detail['rel_path']}.md"
    return f"{folder}/{detail['source_kind']}/{detail['domain_ref_id']}.md"


def _yaml_str(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _frontmatter(detail: dict[str, Any], generated_at: str, card_excerpt_chars: int) -> str:
    lines = ["---", "note_type: source_card",
             f"source_id: {_yaml_str(detail['source_id'])}",
             f"source_kind: {_yaml_str(detail['source_kind'])}"]
    if detail.get("rel_path"):
        lines.append(f"source_path: {_yaml_str(detail['rel_path'])}")
        lines.append(f"source_root_key: {_yaml_str(detail.get('source_root_key'))}")
    else:
        lines.append(f"source_ref_table: {_yaml_str(detail.get('domain_ref_table'))}")
        lines.append(f"source_ref_id: {_yaml_str(detail.get('domain_ref_id'))}")
    lines += [
        f"source_sha256: {_yaml_str(detail.get('content_sha256'))}",
        f"source_mtime_ns: {_yaml_str(detail.get('mtime_ns'))}",
        f"indexed_at: {_yaml_str(detail.get('indexed_at'))}",
        f"generated_at: {_yaml_str(generated_at)}",
        "stale: false",
        f"project_key: {_yaml_str(detail.get('project_key'))}",
        f"project_number: {_yaml_str(detail.get('project_number'))}",
        "tags:",
        f"  - source/{detail['source_kind']}",
    ]
    if detail.get("project_number"):
        lines.append(f"  - project/{detail['project_number']}")
    lines.append("---")
    return "\n".join(lines)


def _render_card(config: ObsidianMcpConfig, detail: dict[str, Any], generated_at: str) -> str:
    cap = int(getattr(config, "source_card_excerpt_chars", 600))
    display = Path(detail["rel_path"]).name if detail.get("rel_path") else str(detail.get("domain_ref_id"))
    parts = [_frontmatter(detail, generated_at, cap), "", f"# Source Card: {display}", ""]

    parts += ["## Overview (deterministic — no model summary)",
              f"- Source kind: {detail['source_kind']}"]
    if detail.get("file_ext"):
        parts.append(f"- Extension: {detail['file_ext']}")
    if detail.get("size_bytes") is not None:
        parts.append(f"- Size (bytes): {detail['size_bytes']}")
    for label, key in (("Pages", "page_count"), ("Paragraphs", "paragraph_count"), ("Sheets", "sheet_count")):
        if detail.get(key) is not None:
            parts.append(f"- {label}: {detail[key]}")
    if detail.get("extraction_status"):
        parts.append(f"- Extraction status: {detail['extraction_status']}")
    if detail.get("project_number"):
        parts.append(f"- Project number: {detail['project_number']}")
    parts.append("")

    # Bounded preview — only for non-sensitive file sources that have indexed text.
    if detail.get("rel_path"):
        if detail.get("text_vault_ref") and not detail.get("text_excerpt"):
            parts += ["## Indexed Text Preview",
                      "_Extracted text is stored encrypted (sensitive source); preview withheld._", ""]
        elif detail.get("text_excerpt"):
            preview = str(detail["text_excerpt"])[:cap]
            truncated = bool(detail.get("excerpt_truncated")) or len(str(detail["text_excerpt"])) > cap
            parts.append("## Indexed Text Preview (bounded — not the full file)")
            parts += [f"> {line}" if line else ">" for line in preview.splitlines()]
            if truncated:
                parts.append(">")
                parts.append("> _(truncated preview of indexed text; the full file stays in its source location)_")
            parts.append("")
    else:
        parts += ["## Linked Record",
                  f"- Reference: `{detail.get('domain_ref_table')}` / `{detail.get('domain_ref_id')}`",
                  "- Body is not stored in this card (link-only source).", ""]

    parts += ["## Source Reference",
              f"- Source ID: `{detail['source_id']}`"]
    if detail.get("rel_path"):
        root = detail.get("source_root_key") or "?"
        parts.append(f"- Original location (outside the vault): root `{root}` -> `{detail['rel_path']}`")
    else:
        parts.append(f"- Linked record: `{detail.get('domain_ref_table')}` id `{detail.get('domain_ref_id')}`")
    parts += [f"- SHA-256: `{detail.get('content_sha256')}`",
              f"- Indexed at: {detail.get('indexed_at')}",
              "",
              "_The raw source remains in its system of record; this card is a curated index entry._",
              ""]
    return "\n".join(parts)


def generate_source_card(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, source_id: str,
                         overwrite: bool = False, principal_kind: str | None = None) -> dict[str, Any]:
    if not getattr(config, "source_card_generation_enabled", True):
        raise ObsidianMcpToolError("source_card_generation_disabled")
    detail = repo.get_source_detail(source_id)
    if detail is None:
        raise ObsidianMcpToolError("source_not_found")
    if detail["source_kind"] == "obsidian_note":
        raise ObsidianMcpToolError("source_card_not_applicable")  # it is already a vault note
    if detail.get("deleted"):
        raise ObsidianMcpToolError("source_deleted")

    generated_at = _now()
    card_rel = _card_rel_path(config, detail)
    content = _render_card(config, detail, generated_at)

    expected_sha: str | None = None
    resolved = resolve_markdown_write_path(config, card_rel, must_exist=False, parent_must_exist=False)
    if resolved.path.exists():
        expected_sha = sha256_file(resolved.path)

    result = create_note(
        config, path=card_rel, content=content, overwrite=overwrite,
        create_parent_dirs=True, expected_sha256=expected_sha,
        caller_surface="mcp", tool_name="generate_source_card", principal_kind=principal_kind,
    )
    repo.record_generated_note(source_id, card_rel, "generated", generated_at)
    return {"source_id": source_id, "note_path": card_rel, "sha256": result["sha256"],
            "overwritten": bool(result.get("overwritten")), "status": "generated"}


def refresh_stale_source_notes(repo: SourceIndexRepository, config: ObsidianMcpConfig, *,
                               max_updates: int = 25, principal_kind: str | None = None) -> dict[str, Any]:
    stale = repo.list_stale_generated_notes(min(max(1, int(max_updates)), 100))
    refreshed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for note in stale:
        try:
            out = generate_source_card(repo, config, source_id=note["source_id"], overwrite=True,
                                       principal_kind=principal_kind)
            refreshed.append({"source_id": note["source_id"], "note_path": out["note_path"]})
        except ObsidianMcpToolError as exc:
            failed.append({"source_id": note["source_id"], "reason": exc.code})
        except Exception as exc:  # never abort the batch on one bad note
            failed.append({"source_id": note["source_id"], "reason": type(exc).__name__})
    return {"refreshed": refreshed, "failed": failed, "count": len(refreshed),
            "max_updates": int(max_updates)}
