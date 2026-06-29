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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import extract, llm, source_analyzers
from .config import ObsidianMcpConfig
from .mutations import create_note, resolve_markdown_write_path, sha256_file
from .source_analyzers import SourceAnalysis
from .source_index_repository import SourceIndexRepository
from .source_indexer import is_excluded_source_path
from .tools import ObsidianMcpToolError

# Bump when the advisory prompt/template changes so receipts record which version produced a card.
# v2: file-type-specific advisory prompts + deterministic per-type analyzer block.
SUMMARY_PROMPT_VERSION = "source-card-v2"
# Construction drawings use a typed PM-summary prompt + schema (separate version for auditability).
DRAWING_PROMPT_VERSION = "source-card-drawing-v1"
# Bid packages / scopes of work use their own typed PM-summary prompt + schema.
BID_PACKAGE_PROMPT_VERSION = "source-card-bid-package-v1"
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


def _frontmatter(detail: dict[str, Any], generated_at: str, advisory: dict[str, Any] | None,
                 analysis: SourceAnalysis | None = None) -> str:
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
    if analysis is not None:
        for key, value in analysis.to_frontmatter_dict().items():
            lines.append(f"{key}: {_yaml_str(value)}")
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


def _md_list(title: str, items: list[str]) -> list[str]:
    """Render a bounded markdown bullet list under a bold label; empty list → nothing."""
    clean = [str(v).strip() for v in (items or []) if str(v).strip()]
    if not clean:
        return []
    return [f"**{title}:**", *[f"- {v}" for v in clean[:_ADVISORY_MAX_ITEMS]], ""]


def _section(title: str, items: list[str]) -> list[str]:
    """Render a `## title` section from a bounded bullet list; empty list → nothing."""
    clean = [str(v).strip() for v in (items or []) if str(v).strip()]
    if not clean:
        return []
    return [f"## {title}", *[f"- {v}" for v in clean[:_ADVISORY_MAX_ITEMS]], ""]


def _render_drawing_advisory(advisory: dict[str, Any]) -> list[str]:
    """PM-facing advisory sections for the typed construction-drawing schema."""
    parts = ["## AI PM Summary (advisory — model-generated, not authoritative)",
             str(advisory.get("plain_english_summary") or "").strip()
             or "_(model returned no summary text)_", ""]
    if str(advisory.get("what_this_sheet_is_for") or "").strip():
        parts += ["## Why This Sheet Matters", str(advisory["what_this_sheet_is_for"]).strip(), ""]
    parts += _section("Scope / Assembly Signals", advisory.get("scope_elements") or [])
    parts += _section("Coordination Items", advisory.get("coordination_items") or [])
    parts += _section("Submittals / Shop Drawings", advisory.get("submittals_or_shop_drawings") or [])
    parts += _section("Field / Procurement Risks", advisory.get("field_installation_risks") or [])
    parts += _section("PM Follow-ups", advisory.get("pm_followups") or [])
    parts += _section("Revision Impacts", advisory.get("revision_impacts") or [])
    verify = list(advisory.get("verify_against_source") or [])
    conf = advisory.get("confidence") or {}
    if conf:
        verify = verify + [
            f"Confidence — sheet identity: {conf.get('sheet_identity', 'low')}, "
            f"scope: {conf.get('scope_summary', 'low')}, action items: {conf.get('action_items', 'low')}."
        ]
    parts += _section("Verification Notes", verify)
    parts += [
        f"_Model: {advisory.get('model_provider')}/{advisory.get('model_name')} · prompt "
        f"{advisory.get('prompt_version')} · generated {advisory.get('generated_at')}. "
        "Advisory only — verify against the source._",
        "",
    ]
    return parts


def _render_drawing_sections(analysis: SourceAnalysis) -> list[str]:
    """Deterministic PM-grade sections for a construction drawing."""
    parts: list[str] = ["## Drawing Identity"]
    parts.append(f"- Document type: {analysis.document_type}")
    parts.append(f"- Discipline: {analysis.discipline}")
    if analysis.sheet_number:
        parts.append(f"- Sheet number: {analysis.sheet_number}")
    if analysis.sheet_title:
        parts.append(f"- Sheet title: {analysis.sheet_title}")
    parts.append("")

    title_block = []
    if analysis.project_name:
        title_block.append(f"Project: {analysis.project_name}")
    if analysis.project_address:
        title_block.append(f"Address: {analysis.project_address}")
    if analysis.issue_status:
        title_block.append(f"Issue status: {analysis.issue_status}")
    if analysis.scale:
        title_block.append(f"Scale: {analysis.scale}")
    parts += _section("Title Block", title_block)

    rev = []
    if analysis.revision_number:
        rev.append(f"Revision: {analysis.revision_number}")
    if analysis.revision_date:
        rev.append(f"Date: {analysis.revision_date}")
    if analysis.revision_description:
        rev.append(f"Description: {analysis.revision_description}")
    parts += _section("Revision / Issue Information", rev)

    parts += _section("Referenced Sheets and Details", analysis.referenced_sheets)
    parts += _section("Numbered Notes / Keynotes", analysis.numbered_notes)
    parts += _section("Rooms / Areas Shown", analysis.spaces)
    parts += _section("Elevation Datums", analysis.datums)
    parts += _section("PM Coordination Flags", analysis.coordination_flags)
    return parts


def _render_fallback_sections(detail: dict[str, Any], analysis: SourceAnalysis) -> list[str]:
    """Deterministic PM-relevant sections for non-drawing documents."""
    identity = [f"Document type: {analysis.document_type}"]
    if analysis.discipline and analysis.discipline != "unknown":
        identity.append(f"Discipline: {analysis.discipline}")
    if detail.get("file_ext"):
        identity.append(f"File type: {detail['file_ext']}")
    parts = _section("Document Identity", identity)

    meta = []
    if analysis.project_name:
        meta.append(f"Project: {analysis.project_name}")
    if analysis.issue_status:
        meta.append(f"Issue status: {analysis.issue_status}")
    if analysis.revision_number:
        meta.append(f"Revision: {analysis.revision_number} {analysis.revision_date or ''}".strip())
    parts += _section("Extracted Metadata", meta)

    signals = list(analysis.coordination_flags) + list(analysis.pm_followup_categories)
    parts += _section("PM-Relevant Signals", signals)
    return parts


def _render_bid_package_sections(detail: dict[str, Any], analysis: SourceAnalysis) -> list[str]:
    """Deterministic PM-grade sections for a bid package / scope-of-work document."""
    identity = [f"Document type: {analysis.document_type}"]
    if detail.get("project_number"):
        identity.append(f"Project number: {detail['project_number']}")
    if analysis.bid_package_number:
        identity.append(f"Package number: {analysis.bid_package_number}")
    if analysis.bid_package_title:
        identity.append(f"Scope / package title: {analysis.bid_package_title}")
    if analysis.issue_status:
        identity.append(f"Issue status: {analysis.issue_status}")
    if detail.get("file_ext"):
        identity.append(f"Source file type: {detail['file_ext']}")
    parts = _section("Bid Package Identity", identity)

    # Scope Summary: prefer extracted inclusions, else the trade scope.
    parts += _section("Scope Summary", list(analysis.inclusions) or list(analysis.trade_scope))
    parts += _section("Inclusions", analysis.inclusions)
    parts += _section("Exclusions", analysis.exclusions)
    parts += _section("Procurement / Estimating Signals", analysis.procurement_signals)
    parts += _section(
        "PM Coordination Flags", list(analysis.trade_scope) + list(analysis.coordination_flags)
    )
    return parts


def _sheet_in_name(name: str, sheet: str) -> bool:
    """True if a filename mentions the sheet number as a standalone token (e.g. 'A-611')."""
    return re.search(r"(?<![A-Z0-9])" + re.escape(sheet) + r"(?![0-9])", name.upper()) is not None


def _match_referenced_sheets(repo: SourceIndexRepository, source_root_key: str | None,
                             project_number: str | None, referenced_sheets: list[str],
                             *, exclude_source_id: str) -> list[dict[str, Any]]:
    """Conservatively match referenced sheet numbers to indexed sources WITHIN THE SAME ROOT.

    Scope order (first non-empty wins): same project folder (project_number) → same root. A scope
    with more than one candidate is ambiguous and left unmatched (rendered as "not found"), never
    matched globally across roots — this avoids cross-project false positives (A-611 is everywhere).
    """
    if not (source_root_key and referenced_sheets):
        return []
    candidates = [c for c in repo.list_root_file_sources(source_root_key)
                  if c["source_id"] != exclude_source_id]
    rels: list[dict[str, Any]] = []
    for sheet in referenced_sheets:
        scoped: tuple[list[dict[str, Any]], str, str] | None = None
        if project_number:
            same_proj = [c for c in candidates if c.get("project_number") == project_number
                         and _sheet_in_name(Path(c["rel_path"]).name, sheet)]
            if same_proj:
                scoped = (same_proj, "project_folder", "high")
        if scoped is None:
            same_root = [c for c in candidates if _sheet_in_name(Path(c["rel_path"]).name, sheet)]
            if same_root:
                scoped = (same_root, "same_root", "medium")
        if scoped is None or len(scoped[0]) != 1:
            continue  # not found or ambiguous → render-only, no relationship row
        target, match_scope, confidence = scoped[0][0], scoped[1], scoped[2]
        rels.append({"dst_kind": "source", "dst_ref": target["source_id"], "relation": "links_to",
                     "confidence": confidence, "evidence": {"sheet": sheet, "match_scope": match_scope}})
    return rels


def _resolve_and_record_relationships(repo: SourceIndexRepository, detail: dict[str, Any],
                                      analysis: SourceAnalysis) -> None:
    """Resolve referenced-sheet links at card-generation time (when the full root is indexed)
    and persist them as ``links_to`` relationship rows. Best-effort; never raises."""
    if not analysis.is_drawing or not analysis.referenced_sheets:
        return
    matched = _match_referenced_sheets(
        repo, detail.get("source_root_key"), detail.get("project_number"),
        analysis.referenced_sheets, exclude_source_id=detail["source_id"],
    )
    if matched:
        repo.record_relationships(detail["source_id"], matched)


def _render_related_sources(repo: SourceIndexRepository, source_id: str,
                            analysis: SourceAnalysis) -> list[str]:
    """`## Related Sources` (matched referenced sheets) + unmatched-reference list."""
    matched_rows = [
        r for r in repo.list_relationships(source_id)
        if r.get("relation") == "links_to" and r.get("dst_kind") == "source"
    ]
    matched_sheets: set[str] = set()
    related: list[str] = []
    for row in matched_rows:
        evidence = row.get("evidence") or {}
        sheet = str(evidence.get("sheet") or "").strip()
        if sheet:
            matched_sheets.add(sheet)
        target = row.get("dst_rel_path") or row.get("dst_ref")
        related.append(f"{sheet + ' → ' if sheet else ''}`{target}`")
    parts = _section("Related Sources", related)
    unmatched = [s for s in analysis.referenced_sheets if s not in matched_sheets]
    parts += _section("Referenced Sheets Not Found in Index", unmatched)
    return parts


def _build_drawing_prompt(detail: dict[str, Any], analysis: SourceAnalysis, text: str) -> str:
    """Compose the model input: deterministic facts FIRST, then the bounded excerpt."""
    facts: list[str] = ["DETERMINISTIC FACTS (extracted — treat as authoritative, do not contradict):"]
    scalar = [
        ("Document type", analysis.document_type), ("Discipline", analysis.discipline),
        ("Sheet number", analysis.sheet_number), ("Sheet title", analysis.sheet_title),
        ("Project", analysis.project_name), ("Issue status", analysis.issue_status),
        ("Scale", analysis.scale),
    ]
    for label, value in scalar:
        if value:
            facts.append(f"- {label}: {value}")
    if analysis.revision_number or analysis.revision_date or analysis.revision_description:
        facts.append(
            f"- Revision: {analysis.revision_number or '?'} / {analysis.revision_date or '?'} / "
            f"{analysis.revision_description or '?'}"
        )
    for label, items in (
        ("Referenced sheets", analysis.referenced_sheets),
        ("Numbered notes", analysis.numbered_notes),
        ("Rooms/areas", analysis.spaces),
        ("Elevation datums", analysis.datums),
        ("Coordination flags", analysis.coordination_flags),
    ):
        if items:
            facts.append(f"- {label}: {', '.join(items)}")
    facts += ["", "BOUNDED TEXT EXCERPT (may be noisy OCR/extraction):", text]
    return "\n".join(facts)


def _build_bid_package_prompt(detail: dict[str, Any], analysis: SourceAnalysis, text: str) -> str:
    """Compose the bid-package model input: deterministic facts FIRST, then the bounded excerpt."""
    facts: list[str] = ["DETERMINISTIC FACTS (extracted — treat as authoritative, do not contradict):"]
    scalar = [
        ("Document type", analysis.document_type),
        ("Project number", detail.get("project_number")),
        ("Package number", analysis.bid_package_number),
        ("Scope / package title", analysis.bid_package_title),
        ("Issue status", analysis.issue_status),
    ]
    for label, value in scalar:
        if value:
            facts.append(f"- {label}: {value}")
    for label, items in (
        ("Inclusions", analysis.inclusions),
        ("Exclusions", analysis.exclusions),
        ("Trade scope", analysis.trade_scope),
        ("Procurement signals", analysis.procurement_signals),
    ):
        if items:
            facts.append(f"- {label}: {', '.join(items)}")
    facts += ["", "BOUNDED TEXT EXCERPT (may be noisy extraction):", text]
    return "\n".join(facts)


def _render_bid_package_advisory(advisory: dict[str, Any]) -> list[str]:
    """PM-facing advisory sections for the typed bid-package schema."""
    parts = ["## AI PM Summary (advisory — model-generated, not authoritative)",
             str(advisory.get("plain_english_summary") or "").strip()
             or "_(model returned no summary text)_", ""]
    parts += _section("Scope Covered", advisory.get("scope_covered") or [])
    parts += _section("Included Work", advisory.get("included_work") or [])
    parts += _section("Excluded / Unclear Work", advisory.get("excluded_or_unclear_work") or [])
    parts += _section("Procurement Risks", advisory.get("procurement_risks") or [])
    parts += _section("Coordination Items", advisory.get("coordination_items") or [])
    parts += _section("Bid Clarifications Needed", advisory.get("bid_clarifications_needed") or [])
    parts += _section("PM Follow-ups", advisory.get("pm_followups") or [])
    verify = list(advisory.get("verify_against_source") or [])
    conf = advisory.get("confidence") or {}
    if conf:
        verify = verify + [
            f"Confidence — package identity: {conf.get('package_identity', 'low')}, "
            f"scope: {conf.get('scope_summary', 'low')}, follow-ups: {conf.get('followups', 'low')}."
        ]
    parts += _section("Verification Notes", verify)
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
                 advisory: dict[str, Any] | None = None, *,
                 repo: SourceIndexRepository | None = None) -> str:
    cap = int(getattr(config, "source_card_excerpt_chars", 600))
    display = Path(detail["rel_path"]).name if detail.get("rel_path") else str(detail.get("domain_ref_id"))
    # Deterministic construction analysis (file sources only; sensitive sources have no excerpt).
    analysis = source_analyzers.from_detail(detail) if detail.get("rel_path") else None
    parts = [_frontmatter(detail, generated_at, advisory, analysis), "", f"# Source Card: {display}", ""]
    if advisory:
        kind = advisory.get("kind")
        if kind == "drawing":
            parts += _render_drawing_advisory(advisory)
        elif kind == "bid_package":
            parts += _render_bid_package_advisory(advisory)
        else:
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

    # PM-grade deterministic sections: drawing-specific, bid-package, or general-document fallback.
    if analysis is not None:
        if analysis.is_drawing:
            parts += _render_drawing_sections(analysis)
            if repo is not None:
                parts += _render_related_sources(repo, detail["source_id"], analysis)
        elif analysis.is_bid_package:
            parts += _render_bid_package_sections(detail, analysis)
        else:
            parts += _render_fallback_sections(detail, analysis)

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
    if detail.get("rel_path") and is_excluded_source_path(str(detail["rel_path"]), config):
        raise ObsidianMcpToolError("source_excluded_path")  # low-value dependency/build tree

    generated_at = _now()
    card_rel = _card_rel_path(config, detail)
    # Resolve referenced-sheet links now (the whole root is indexed by card-generation time) so the
    # rendered "Related Sources" reflects current matches.
    _resolve_and_record_relationships(repo, detail, source_analyzers.from_detail(detail))
    content = _render_card(config, detail, generated_at, repo=repo)

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

    card_rel = _card_rel_path(config, detail)
    if detail.get("rel_path") and is_excluded_source_path(str(detail["rel_path"]), config):
        # Excluded dependency/build tree: no card, and never call the model.
        return {"summarized": False, "reason": "excluded_path",
                "source_id": source_id, "note_path": card_rel}

    # One-call contract: ensure the deterministic base card exists first (generate if missing).
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
    analysis = source_analyzers.from_detail(detail)
    _resolve_and_record_relationships(repo, detail, analysis)

    if analysis.is_drawing:
        # Typed PM-summary path: the model receives deterministic facts + the bounded excerpt and
        # emits the strict drawing schema. Prompt version is distinct for auditability.
        prompt_input = _build_drawing_prompt(detail, analysis, text)
        data, mode, reason = llm.summarize_drawing(config, prompt_text=prompt_input, backend=backend)
        prompt_version = DRAWING_PROMPT_VERSION
        summary_text_for_sha = "" if data is None else str(data.get("plain_english_summary") or "")
    elif analysis.is_bid_package:
        # Typed bid-package PM-summary path (own schema + prompt version for auditability).
        prompt_input = _build_bid_package_prompt(detail, analysis, text)
        data, mode, reason = llm.summarize_bid_package(config, prompt_text=prompt_input, backend=backend)
        prompt_version = BID_PACKAGE_PROMPT_VERSION
        summary_text_for_sha = "" if data is None else str(data.get("plain_english_summary") or "")
    else:
        deterministic = extract.analyze(rel, text, max_chars=cap)
        result, mode, reason = llm.summarize(
            config, text=text, deterministic=deterministic, backend=backend,
            file_ext=detail.get("file_ext"),
        )
        data = result if mode == "llm" else None
        prompt_version = SUMMARY_PROMPT_VERSION
        summary_text_for_sha = "" if data is None else str(data.get("summary") or "")

    if mode != "llm":
        # Ollama unavailable / fallback: the deterministic base card stands; no advisory written.
        # ``reason`` is a specific category (timeout / invalid_json / empty_response /
        # ollama_unavailable / disabled) so the operator can tell why summarization fell back.
        return {"summarized": False, "reason": reason, "mode": mode,
                "source_id": source_id, "note_path": card_rel}

    generated_at = _now()
    model_meta = {
        "model_provider": config.summarization_provider,
        "model_name": config.summarization_model,
        "prompt_version": prompt_version,
        "generated_at": generated_at,
    }
    if analysis.is_drawing:
        advisory = {"kind": "drawing", **dict(data or {}), **model_meta}
    elif analysis.is_bid_package:
        advisory = {"kind": "bid_package", **dict(data or {}), **model_meta}
    else:
        advisory = {
            "summary": (data or {}).get("summary", ""),
            "key_points": (data or {}).get("key_points", []),
            "action_items": (data or {}).get("action_items", []),
            "decisions": (data or {}).get("decisions", []),
            "entities": (data or {}).get("entities", []),
            **model_meta,
        }
    content = _render_card(config, detail, generated_at, advisory=advisory, repo=repo)

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
        "prompt_version": prompt_version,
        "prompt_sha256": _sha256_text(f"{prompt_version}|{text}"),
        "summary_sha256": _sha256_text(summary_text_for_sha),
        "source_sha256": detail.get("content_sha256"),
    })
    return {"summarized": True, "source_id": source_id, "note_path": card_rel,
            "sha256": result_write["sha256"], "mode": "llm",
            "model_provider": config.summarization_provider, "model_name": config.summarization_model,
            "prompt_version": prompt_version}
