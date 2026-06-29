"""Obsidian source cards: deterministic base + optional advisory model summary.

A source card describes and links back to an indexed source — NOT a copy of it. The base card
is fully deterministic (no model output). ``summarize_source`` may add an OPTIONAL advisory
section produced by a local model (Ollama), clearly labelled and never authoritative; the
deterministic tools (``generate_source_card``/``refresh_stale_source_notes``) never emit model
content and strip any advisory section. No raw file dumping (bounded labelled preview, withheld
for sensitive sources). No raw email body (link sources have no extracted text). Cards are
written through the existing ``create_note`` guardrails (write policy, SHA-gated overwrite,
atomic write, backup, receipt, pathsafe).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import extract, llm
from .config import ObsidianMcpConfig
from .mutations import create_note, resolve_markdown_write_path, sha256_file
from .source_index_repository import SourceIndexRepository
from .tools import ObsidianMcpToolError

# Bump when the advisory prompt/template changes so receipts record which version produced a card.
# v2: file-type-specific advisory prompts + deterministic per-type analyzer block.
SUMMARY_PROMPT_VERSION = "source-card-v2"
_ADVISORY_LIST_KEYS = ("key_points", "action_items", "decisions", "entities")
_ADVISORY_MAX_ITEMS = 10
_ADVISORY_ITEM_CHARS = 200


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _frontmatter(detail: dict[str, Any], generated_at: str, advisory: dict[str, Any] | None) -> str:
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
    ]
    lines.append(f"summary_advisory: {'true' if advisory else 'false'}")
    if advisory:
        lines += [
            f"summary_model_provider: {_yaml_str(advisory.get('model_provider'))}",
            f"summary_model_name: {_yaml_str(advisory.get('model_name'))}",
            f"summary_prompt_version: {_yaml_str(advisory.get('prompt_version'))}",
            f"summary_generated_at: {_yaml_str(advisory.get('generated_at'))}",
        ]
    lines += ["tags:", f"  - source/{detail['source_kind']}"]
    if detail.get("project_number"):
        lines.append(f"  - project/{detail['project_number']}")
    if advisory:
        lines.append("  - source/ai-summarized")
    lines.append("---")
    return "\n".join(lines)


def _render_advisory(advisory: dict[str, Any]) -> list[str]:
    parts = ["## AI Summary (advisory — model-generated, not authoritative)",
             str(advisory.get("summary") or "").strip() or "_(model returned no summary text)_", ""]
    for key in _ADVISORY_LIST_KEYS:
        items = [str(v).strip()[:_ADVISORY_ITEM_CHARS] for v in (advisory.get(key) or []) if str(v).strip()]
        if items:
            parts.append(f"**{key.replace('_', ' ').title()}:**")
            parts += [f"- {item}" for item in items[:_ADVISORY_MAX_ITEMS]]
            parts.append("")
    parts += [
        f"_Model: {advisory.get('model_provider')}/{advisory.get('model_name')} · prompt "
        f"{advisory.get('prompt_version')} · generated {advisory.get('generated_at')}. "
        "Advisory only — verify against the source._",
        "",
    ]
    return parts


_FILE_TYPE_LABELS = {
    "md": "Markdown note", "markdown": "Markdown note", "txt": "Plain-text file",
    "pdf": "PDF document", "docx": "Word document", "xlsx": "Excel workbook",
    "csv": "CSV table", "pptx": "PowerPoint deck",
}


def _heading_outline(text: str, *, limit: int = 8) -> list[str]:
    """First few Markdown headings from indexed text, as an indented outline (bounded)."""
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            if title:
                out.append(f"  {'  ' * (level - 1)}- {title[:120]}")
        if len(out) >= limit:
            break
    return out


def _analyzer_block(detail: dict[str, Any]) -> list[str]:
    """Deterministic, file-type-specific evidence derived from existing index metadata.

    Uses only ``source_intelligence_metadata`` fields (file_ext, page/paragraph/sheet counts,
    extraction_status) plus, for non-sensitive markdown, a bounded heading outline from the
    indexed excerpt. Never dumps the file; sensitive sources have no excerpt so no outline.
    """
    ext = (detail.get("file_ext") or "").lower()
    label = _FILE_TYPE_LABELS.get(ext, f"{ext.upper()} file" if ext else "Unknown file type")
    status = detail.get("extraction_status")
    has_text = bool(detail.get("text_excerpt"))
    lines = [f"## File Analysis — {label}"]

    if ext in {"md", "markdown"}:
        if has_text:
            outline = _heading_outline(str(detail["text_excerpt"]))
            if outline:
                lines.append("- Heading outline:")
                lines += outline
            else:
                lines.append("- No Markdown headings detected in the indexed excerpt.")
        if detail.get("paragraph_count") is not None:
            lines.append(f"- Paragraphs: {detail['paragraph_count']}")
    elif ext == "txt":
        lines.append("- Plain text (no structure extracted).")
        if detail.get("paragraph_count") is not None:
            lines.append(f"- Paragraphs: {detail['paragraph_count']}")
    elif ext == "pdf":
        if detail.get("page_count") is not None:
            lines.append(f"- Pages: {detail['page_count']}")
        if status == "ok" and has_text:
            lines.append("- Contains extractable text (text-based PDF).")
        elif status in {"failed", "unsupported"} or not has_text:
            lines.append("- No extractable text — likely a scanned/image-only PDF.")
    elif ext == "docx":
        if detail.get("paragraph_count") is not None:
            lines.append(f"- Paragraphs: {detail['paragraph_count']}")
        lines.append("- Word document (styles/tables not separately indexed).")
    elif ext == "xlsx":
        if detail.get("sheet_count") is not None:
            lines.append(f"- Sheets: {detail['sheet_count']}")
        lines.append("- Spreadsheet workbook (cell-level data not indexed).")
    elif ext == "csv":
        lines.append("- Tabular CSV (column/row structure not separately indexed).")
    else:
        lines.append("- Binary or unsupported file type — indexed as metadata/link only.")
        if status:
            lines.append(f"- Extraction status: {status}")
    lines.append("")
    return lines


def _render_card(config: ObsidianMcpConfig, detail: dict[str, Any], generated_at: str,
                 advisory: dict[str, Any] | None = None) -> str:
    cap = int(getattr(config, "source_card_excerpt_chars", 600))
    display = Path(detail["rel_path"]).name if detail.get("rel_path") else str(detail.get("domain_ref_id"))
    parts = [_frontmatter(detail, generated_at, advisory), "", f"# Source Card: {display}", ""]
    if advisory:
        parts += _render_advisory(advisory)

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

    # File-type-specific deterministic evidence (file sources only).
    if detail.get("rel_path"):
        parts += _analyzer_block(detail)

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
    # Deterministic card carries no advisory section -> drop any prior model-summary receipt.
    repo.delete_summary(source_id)
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


def _source_input_text(detail: dict[str, Any]) -> str | None:
    """Bounded text the model summarizes. None for sensitive/link sources (no usable text)."""
    if not detail.get("rel_path"):
        return None  # link sources (email/procore/schedule) carry no extracted text
    if detail.get("text_vault_ref") and not detail.get("text_excerpt"):
        return None  # sensitive: indexed text is encrypted; do not feed it to the model here
    return str(detail.get("text_excerpt") or "").strip() or None


def summarize_source(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, source_id: str,
                     principal_kind: str | None = None, backend: Any = None) -> dict[str, Any]:
    """Model-assisted advisory enrichment of a source card. One call: generates the deterministic
    base if missing, then (only when a real model produced output) writes an advisory section in
    place. Never blocks on Ollama; falls back to ``summarized: false`` when unavailable."""
    if not getattr(config, "source_summary_enabled", True):
        raise ObsidianMcpToolError("source_summary_disabled")
    detail = repo.get_source_detail(source_id)
    if detail is None:
        raise ObsidianMcpToolError("source_not_found")
    if detail["source_kind"] == "obsidian_note":
        raise ObsidianMcpToolError("source_card_not_applicable")
    if detail.get("deleted"):
        raise ObsidianMcpToolError("source_deleted")

    # One-call contract: ensure the deterministic base card exists first (generate if missing).
    card_rel = _card_rel_path(config, detail)
    resolved = resolve_markdown_write_path(config, card_rel, must_exist=False, parent_must_exist=False)
    if not resolved.path.exists():
        generate_source_card(repo, config, source_id=source_id, overwrite=False,
                             principal_kind=principal_kind)

    text = _source_input_text(detail)
    if not text:  # sensitive / link source: base card exists, but no text to summarize
        return {"summarized": False, "reason": "no_summarizable_text",
                "source_id": source_id, "note_path": card_rel}

    cap = int(getattr(config, "source_summary_max_input_chars", 6000))
    text = text[:cap]
    rel = str(detail.get("rel_path"))
    deterministic = extract.analyze(rel, text, max_chars=cap)
    result, mode, reason = llm.summarize(
        config, text=text, deterministic=deterministic, backend=backend,
        file_ext=detail.get("file_ext"),
    )
    if mode != "llm":
        # Ollama unavailable / fallback: the deterministic base card stands; no advisory written.
        # ``reason`` is a specific category (timeout / invalid_json / empty_response /
        # ollama_unavailable / disabled) so the operator can tell why summarization fell back.
        return {"summarized": False, "reason": reason, "mode": mode,
                "source_id": source_id, "note_path": card_rel}

    generated_at = _now()
    advisory = {
        "summary": result.get("summary", ""),
        "key_points": result.get("key_points", []),
        "action_items": result.get("action_items", []),
        "decisions": result.get("decisions", []),
        "entities": result.get("entities", []),
        "model_provider": config.summarization_provider,
        "model_name": config.summarization_model,
        "prompt_version": SUMMARY_PROMPT_VERSION,
        "generated_at": generated_at,
    }
    content = _render_card(config, detail, generated_at, advisory=advisory)

    resolved = resolve_markdown_write_path(config, card_rel, must_exist=False, parent_must_exist=False)
    exists = resolved.path.exists()
    result_write = create_note(
        config, path=card_rel, content=content, overwrite=exists,
        create_parent_dirs=True, expected_sha256=sha256_file(resolved.path) if exists else None,
        caller_surface="mcp", tool_name="summarize_source", principal_kind=principal_kind,
    )
    repo.record_generated_note(source_id, card_rel, "generated", generated_at)
    repo.upsert_summary(source_id, {
        "model_provider": config.summarization_provider,
        "model_name": config.summarization_model,
        "prompt_version": SUMMARY_PROMPT_VERSION,
        "prompt_sha256": _sha256_text(f"{SUMMARY_PROMPT_VERSION}|{text}"),
        "summary_sha256": _sha256_text(str(advisory["summary"])),
        "source_sha256": detail.get("content_sha256"),
    })
    return {"summarized": True, "source_id": source_id, "note_path": card_rel,
            "sha256": result_write["sha256"], "mode": "llm",
            "model_provider": config.summarization_provider, "model_name": config.summarization_model,
            "prompt_version": SUMMARY_PROMPT_VERSION}
