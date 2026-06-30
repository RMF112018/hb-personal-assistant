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
from .source_indexer import is_deferred_source_path, is_excluded_source_path
from .source_value import SourceValue, classify_source_value, derive_confidence
from .tools import ObsidianMcpToolError

# Card schema markers (kept in sync with Templates/Source Cards/source-card-template.md).
TEMPLATE_VERSION = "source-card-v1"
CARD_VERSION = "phase8-v1"
# document_type values that are not a confident PM class → flag the card for human review.
# template_form is ambiguous-by-design: a blank instrument needs a human to confirm blank-vs-executed.
_AMBIGUOUS_DOC_TYPES = frozenset({
    "general_pdf", "general_document", "spreadsheet", "cost_document", "template_form",
})


def _domain_for(detail: dict[str, Any]) -> str:
    """Deterministic work/home/shared domain from the source root key (no path content needed).

    Single source of truth for both the card frontmatter `domain` and the routed Source Notes
    subfolder. Home is checked first so a hypothetical 'home-work' key resolves to home.
    """
    key = str(detail.get("source_root_key") or "").lower()
    if "home" in key:
        return "home"
    if any(s in key for s in ("onedrive", "work", "syn-work", "hb-", "procore", "sharepoint")):
        return "work"
    return "shared"


# work/home/shared (lowercase, from _domain_for) -> the seeded vault subfolder name.
_DOMAIN_FOLDER = {"work": "Work", "home": "Home", "shared": "Shared"}
_SAFE_BASENAME_RE = re.compile(r"[^A-Za-z0-9 _.()\-]+")
_MAX_BASENAME_CHARS = 80


def _safe_basename(detail: dict[str, Any]) -> str:
    """A readable, path-safe card basename derived from the source filename (NOT its directory path).

    Guarantees: no path separators, no '..', no leading dot/dotfile, no absolute-path fragment, no
    control characters, bounded length; deterministic 'source' fallback when empty. The
    ``__<source_id>.md`` suffix is appended by the caller AFTER this, so the suffix is never altered.
    """
    if detail.get("rel_path"):
        raw = Path(str(detail["rel_path"]).replace("\\", "/")).name  # basename only — drops directories
    else:
        raw = f"{detail.get('source_kind') or 'link'}__{detail.get('domain_ref_id') or ''}"
    raw = raw.replace("\\", "/").replace("/", " ")          # belt-and-suspenders: no separators
    raw = "".join(ch for ch in raw if ch.isprintable() and ch not in "\t\r\n")  # no control chars
    raw = _SAFE_BASENAME_RE.sub("-", raw)                    # whitelist charset
    raw = re.sub(r"\.{2,}", ".", raw)                        # collapse runs of dots (kills '..')
    raw = re.sub(r"[-\s]{2,}", lambda m: m.group(0)[0], raw)  # collapse repeated separators
    raw = raw.strip(" .-")                                    # no leading/trailing dot/space/dash
    raw = raw[:_MAX_BASENAME_CHARS].strip(" .-")
    return raw or "source"

# Bump when the advisory prompt/template changes so receipts record which version produced a card.
# v2: file-type-specific advisory prompts + deterministic per-type analyzer block.
SUMMARY_PROMPT_VERSION = "source-card-v2"
# Construction drawings use a typed PM-summary prompt + schema (separate version for auditability).
DRAWING_PROMPT_VERSION = "source-card-drawing-v1"
# Bid packages / scopes of work use their own typed PM-summary prompt + schema.
BID_PACKAGE_PROMPT_VERSION = "source-card-bid-package-v1"
_ADVISORY_MAX_ITEMS = 10


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _card_rel_path(config: ObsidianMcpConfig, detail: dict[str, Any]) -> str:
    """Routed, path-safe generated-card path: ``<folder>/<Domain>/<basename>__<source_id12>.md``.

    Routes by the deterministic :func:`_domain_for` domain. The source directory path is NOT
    replicated and never embedded in the filename; the 12-char source_id suffix makes the path stable
    per source and collision-safe across same-basename sources (preserving the
    UNIQUE(source_id, note_rel_path) model).
    """
    folder = (config.source_notes_folder or "Source Notes").strip("/")
    domain_folder = _DOMAIN_FOLDER.get(_domain_for(detail), "Shared")
    source_id12 = str(detail["source_id"])[:12]
    return f"{folder}/{domain_folder}/{_safe_basename(detail)}__{source_id12}.md"


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
                 analysis: SourceAnalysis | None = None, *,
                 value: SourceValue | None = None, domain: str = "shared",
                 review_status: str = "unreviewed", confidence: str | None = None) -> str:
    lines = ["---", "note_type: source_card",
             f"domain: {_yaml_str(domain)}",
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
        f"updated_at: {_yaml_str(detail.get('updated_at') or detail.get('indexed_at') or generated_at)}",
        f"generated_at: {_yaml_str(generated_at)}",
        "stale: false",
        f"project_key: {_yaml_str(detail.get('project_key'))}",
        f"project_number: {_yaml_str(detail.get('project_number'))}",
    ]
    if analysis is not None:
        for key, val in analysis.to_frontmatter_dict().items():
            lines.append(f"{key}: {_yaml_str(val)}")
    if value is not None:
        lines.append(f"source_disposition: {_yaml_str(value.disposition.value)}")
    if confidence is not None:
        lines.append(f"source_confidence: {_yaml_str(confidence)}")
    lines += [
        f"review_status: {_yaml_str(review_status)}",
        f"template_version: {_yaml_str(TEMPLATE_VERSION)}",
        f"card_version: {_yaml_str(CARD_VERSION)}",
    ]
    lines.append(f"summary_advisory: {'true' if advisory else 'false'}")
    if advisory:
        lines += [
            f"summary_model_provider: {_yaml_str(advisory.get('model_provider'))}",
            f"summary_model_name: {_yaml_str(advisory.get('model_name'))}",
            f"summary_prompt_version: {_yaml_str(advisory.get('prompt_version'))}",
            f"summary_generated_at: {_yaml_str(advisory.get('generated_at'))}",
        ]
    lines += ["tags:", f"  - source/{detail['source_kind']}", f"  - domain/{domain}"]
    if detail.get("project_number"):
        lines.append(f"  - project/{detail['project_number']}")
    if advisory:
        lines.append("  - source/ai-summarized")
    lines.append("---")
    return "\n".join(lines)


def _md_list(title: str, items: list[str]) -> list[str]:
    """Render a bounded markdown bullet list under a bold label; empty list → nothing."""
    clean = [str(v).strip() for v in (items or []) if str(v).strip()]
    if not clean:
        return []
    return [f"**{title}:**", *[f"- {v}" for v in clean[:_ADVISORY_MAX_ITEMS]], ""]


def _card_basis(detail: dict[str, Any]) -> str:
    """How this card was produced (A1.11): full text, spreadsheet metadata, metadata, or filename."""
    ext = (detail.get("file_ext") or "").lower()
    has_text = bool(detail.get("text_excerpt"))
    if ext in ("xlsx", "xlsm"):
        return "spreadsheet metadata + bounded cell sample"
    if detail.get("text_vault_ref") and not has_text:
        return "metadata only (sensitive source — extracted text withheld)"
    if has_text:
        return "full extracted text (bounded)"
    if detail.get("extraction_status") in ("failed", "unsupported", "skipped_too_large") or not has_text:
        return "filename/path analysis + metadata only"
    return "metadata only"


# Deterministic, document-type-specific PM guidance (NO model output). Drives the Why This Matters /
# PM Review Cues / Follow-Up sections so cards carry real PM signal instead of boilerplate.
_PM_GUIDANCE: dict[str, dict[str, list[str]]] = {
    "change_order": {
        "why": ["An executed change order moves contract value and scope of record."],
        "cues": ["Confirm this is executed (not a request or a template).",
                 "Verify the amount and the scope/justification basis.",
                 "Tie it to the originating RFI / PCO / ASI / submittal."],
        "followup": ["Confirm executed status and amount against the source.",
                     "Link the originating change event and the affected budget line."],
    },
    "potential_change_order": {
        "why": ["A potential change order (PCO/COR) tracks pricing and approval before it executes."],
        "cues": ["Confirm the pricing basis and current approval state.",
                 "Tie it to the originating change event / RFI."],
        "followup": ["Track pricing and approval through to a decision.",
                     "Link the originating change event / RFI."],
    },
    "pay_application": {
        "why": ["A payment application drives billing and cash; figures must be verified."],
        "cues": ["Verify the application amount and billing period.",
                 "Confirm the approval/certification state and retainage."],
        "followup": ["Reconcile the amount and period against the schedule of values.",
                     "Confirm certification before relying on the figures."],
    },
    "purchase_order": {
        "why": ["A purchase order is committed procurement; vendor and amount matter."],
        "cues": ["Verify the vendor and committed amount.",
                 "Confirm the PO number ties to the right cost code."],
        "followup": ["Confirm vendor, amount, and cost-code tie-out."],
    },
    "subcontract": {
        "why": ["A subcontract defines a trade partner's scope, value, and terms."],
        "cues": ["Confirm the subcontractor, value, and scope of work.",
                 "Check that exhibits/exclusions are attached."],
        "followup": ["Confirm executed value and scope; verify required exhibits."],
    },
    "contract": {
        "why": ["A contract defines obligations, value, and terms of record."],
        "cues": ["Confirm parties, value, and key terms.",
                 "Confirm execution state (executed vs draft)."],
        "followup": ["Confirm execution and value; file the conformed copy."],
    },
    "rfi": {
        "why": ["An RFI is an open question that can affect cost/schedule until answered."],
        "cues": ["Confirm the RFI number and whether it is open or closed.",
                 "Check the cost/schedule impact and the responsible party."],
        "followup": ["Confirm status (open/closed) and any cost/schedule impact.",
                     "Link the resulting change event if one was issued."],
    },
    "submittal": {
        "why": ["A submittal gates procurement and installation through product/shop-drawing approval."],
        "cues": ["Confirm the submittal/spec section and the review status.",
                 "Reject any status read from a dropdown/template — confirm the real disposition."],
        "followup": ["Confirm the review disposition and the governing spec section."],
    },
    "schedule": {
        "why": ["A schedule artifact carries sequencing and milestones (no CPM computed here)."],
        "cues": ["Confirm the data date and whether this is baseline or an update.",
                 "Check critical-path milestones and total float."],
        "followup": ["Confirm data date and baseline-vs-update; review critical path and float."],
    },
    "specification": {
        "why": ["A specification governs materials and workmanship requirements."],
        "cues": ["Confirm the spec section and revision/addendum state."],
        "followup": ["Confirm the governing section and current revision/addenda."],
    },
    "drawing": {
        "why": ["A drawing carries design intent; coordinate against current revisions."],
        "cues": ["Confirm the sheet number, title, and revision/date.",
                 "Drawing content is not text-extracted — verify against the actual sheet."],
        "followup": ["Confirm sheet identity and current revision against the issued set."],
    },
    "bid_package": {
        "why": ["A bid package defines a procurement scope for pricing."],
        "cues": ["Confirm inclusions, exclusions, alternates, and allowances.",
                 "Check that all addenda are incorporated."],
        "followup": ["Confirm scope inclusions/exclusions and that addenda are incorporated."],
    },
    "daily_log": {
        "why": ["A daily log is the field record of labor and conditions for the day."],
        "cues": ["Confirm the date and the crews/conditions recorded."],
        "followup": ["Confirm date and crew/condition entries if used as a claim record."],
    },
    "manpower_log": {
        "why": ["A manpower/labor log is a staffing record affecting productivity tracking."],
        "cues": ["Confirm the period and the headcount/hours recorded."],
        "followup": ["Confirm period and hours before using for productivity analysis."],
    },
    "cost_report": {
        "why": ["A cost report is the current cost position; reconcile against budget/forecast."],
        "cues": ["Confirm the reporting period and the cost-to-date basis.",
                 "Reconcile against the budget and forecast of record."],
        "followup": ["Reconcile the period figures against budget and forecast."],
    },
    "project_controls": {
        "why": ["A project-controls report is the cost/forecast position of record."],
        "cues": ["Confirm the period and the forecast basis."],
        "followup": ["Confirm the forecast basis and period before relying on it."],
    },
    "staffing_report": {
        "why": ["A staffing/labor workbook tracks planned-vs-actual labor."],
        "cues": ["Confirm the period and the planned-vs-actual basis."],
        "followup": ["Confirm period and basis before productivity analysis."],
    },
    "closeout": {
        "why": ["A closeout document is a completion/handover record."],
        "cues": ["Confirm completeness against the closeout checklist."],
        "followup": ["Confirm completeness against the closeout requirements."],
    },
    "warranty": {
        "why": ["A warranty document defines coverage and obligations after completion."],
        "cues": ["Confirm coverage scope, term, and start date."],
        "followup": ["Confirm coverage term and start date; file with O&M."],
    },
    "operations_maintenance": {
        "why": ["An O&M document is operations/maintenance reference for handover."],
        "cues": ["Confirm the systems covered and that it is the final issue."],
        "followup": ["Confirm coverage and final-issue status for handover."],
    },
    "punch_list": {
        "why": ["A punch list is open completion items before final acceptance."],
        "cues": ["Confirm the area/scope and open-vs-closed item state."],
        "followup": ["Track open items to closure before final acceptance."],
    },
    "safety": {
        "why": ["A safety record is compliance and risk documentation."],
        "cues": ["Confirm the date and the activity/inspection recorded."],
        "followup": ["Confirm date and follow up on any noted hazards."],
    },
    "quality": {
        "why": ["A quality record is conformance / QA-QC documentation."],
        "cues": ["Confirm any non-conformance and its disposition."],
        "followup": ["Track any non-conformance to disposition."],
    },
    "inspection": {
        "why": ["An inspection record verifies work/compliance."],
        "cues": ["Confirm the inspection result (pass/fail) and date."],
        "followup": ["Confirm result and follow up on any deficiencies."],
    },
    "meeting_minutes": {
        "why": ["Meeting minutes capture decisions and action items of record."],
        "cues": ["Confirm the meeting date and the open action items/owners."],
        "followup": ["Track open action items and owners to closure."],
    },
    "template_form": {
        "why": ["A blank template/form — reference only, NOT a live instrument or status evidence."],
        "cues": ["Confirm this is a blank template, not a completed/executed document.",
                 "Do not treat any value on it (status, amount, date) as project data."],
        "followup": ["Confirm blank-vs-executed; do not record any value from a template."],
    },
    "cost_document": {
        "why": ["A cost-related document — reconcile any figures against the records of account."],
        "cues": ["Confirm the figures against the budget/forecast of record."],
        "followup": ["Reconcile figures against the records of account."],
    },
    "spreadsheet": {
        "why": ["A workbook retained for reference; no high-value cost/pay class was detected."],
        "cues": ["Confirm the workbook's purpose and verify figures against the source."],
        "followup": ["Confirm purpose; verify any figures before relying on them."],
    },
}
_PM_GUIDANCE_FALLBACK = {
    "why": ["Indexed source retained for reference and search; classification is low-signal."],
    "cues": ["Open the source and confirm what it is before relying on this card."],
    "followup": ["Confirm the document type and key facts against the source."],
}

# Workbook signal terms surfaced as Key Facts for spreadsheets (metadata + bounded cell sample only).
_SPREADSHEET_SIGNAL_TERMS = (
    "pay app", "payment application", "cost", "budget", "forecast", "staffing", "manpower",
    "labor", "schedule", "total", "subtotal", "contract", "change order",
)


def _pm_guidance(doc_type: str | None) -> dict[str, list[str]]:
    """Deterministic PM guidance for a document type (drawing disciplines + bid types normalized)."""
    if doc_type in source_analyzers.DRAWING_DOCUMENT_TYPES:
        doc_type = "drawing"
    elif doc_type in source_analyzers.BID_DOCUMENT_TYPES:
        doc_type = "bid_package"
    elif doc_type in ("general_pdf", "general_document", "presentation", "marketing", "site_map"):
        return _PM_GUIDANCE_FALLBACK
    return _PM_GUIDANCE.get(doc_type or "", _PM_GUIDANCE_FALLBACK)


def _source_summary_lines(detail: dict[str, Any], analysis: SourceAnalysis | None) -> list[str]:
    """Deterministic 1–2 line summary (source kind/ext/size/counts/extraction/type). NOT raw body."""
    if not detail.get("rel_path"):
        return [f"- Linked record: `{detail.get('domain_ref_table')}` / `{detail.get('domain_ref_id')}` "
                f"(source kind: {detail['source_kind']}); body is not stored in this card.",
                f"- Document type: {analysis.document_type if analysis else 'linked_record'} "
                "(deterministic — metadata)"]
    ext = (detail.get("file_ext") or "").lower()
    label = _FILE_TYPE_LABELS.get(ext, f"{ext.upper()} file" if ext else "Unknown file type")
    bits = [label]
    if detail.get("size_bytes") is not None:
        bits.append(f"{detail['size_bytes']} bytes")
    for word, key in (("pages", "page_count"), ("sheets", "sheet_count"),
                      ("paragraphs", "paragraph_count")):
        if detail.get(key) is not None:
            bits.append(f"{detail[key]} {word}")
    if detail.get("extraction_status"):
        bits.append(f"extraction {detail['extraction_status']}")
    doc_type = analysis.document_type if analysis else "unknown"
    return [f"- {' · '.join(bits)}",
            f"- Document type: {doc_type} (deterministic — filename/metadata)"]


def _review_cues(detail: dict[str, Any], analysis: SourceAnalysis | None,
                 guidance: dict[str, list[str]], review_status: str) -> list[str]:
    """Type-specific cues + dynamic cues from the deterministic fields + a needs-review note."""
    cues: list[str] = list(guidance["cues"])
    if analysis and analysis.document_number:
        cues.append(f"Confirm document number {analysis.document_number}.")
    if analysis and analysis.amount:
        cues.append(f"Verify amount {analysis.amount} against the source (deterministic extract).")
    if analysis and analysis.doc_status:
        cues.append(f"Confirm status '{analysis.doc_status}'.")
    if detail.get("project_number"):
        cues.append(f"Tie to project {detail['project_number']}.")
    if review_status == "needs_review":
        cues.append("Low-confidence / ambiguous classification — confirm the document type first.")
    return cues


def _referenced_sheet_facts(repo: SourceIndexRepository | None, source_id: str,
                            analysis: SourceAnalysis) -> list[str]:
    """One Key-Facts line listing referenced sheets, marking which resolved to an indexed source."""
    if not analysis.referenced_sheets:
        return []
    linked: dict[str, str] = {}
    if repo is not None:
        for row in repo.list_relationships(source_id):
            if row.get("relation") == "links_to" and row.get("dst_kind") == "source":
                evidence = row.get("evidence") or {}
                sheet = str(evidence.get("sheet") or "").strip()
                if sheet:
                    linked[sheet] = str(row.get("dst_rel_path") or row.get("dst_ref") or "")
    rendered: list[str] = []
    for sheet in analysis.referenced_sheets[:_ADVISORY_MAX_ITEMS]:
        if sheet in linked and linked[sheet]:
            rendered.append(f"{sheet} → `{linked[sheet]}` (linked in index)")
        else:
            rendered.append(f"{sheet} (not linked in index)")
    return ["Referenced sheets: " + "; ".join(rendered)]


def _key_facts(detail: dict[str, Any], analysis: SourceAnalysis | None,
               repo: SourceIndexRepository | None) -> list[str]:
    """Deterministic fields + folded type-specific facts (drawing/bid/spreadsheet). Never empty."""
    facts: list[str] = []
    if detail.get("project_number"):
        facts.append(f"Project number: {detail['project_number']}")
    if analysis is not None:
        for label, val in (("Document number", analysis.document_number), ("Title", analysis.title),
                           ("Vendor", analysis.vendor), ("Amount", analysis.amount),
                           ("Date", analysis.doc_date), ("Status", analysis.doc_status)):
            if val:
                facts.append(f"{label}: {val}")
        ext = (detail.get("file_ext") or "").lower()
        if analysis.is_drawing:
            facts += _drawing_facts(detail, analysis, repo)
        elif analysis.is_bid_package:
            facts += _bid_facts(analysis)
        elif ext in ("xlsx", "xlsm"):
            facts += _spreadsheet_facts(detail, analysis)
    if not facts:
        facts.append("No deterministic key facts extracted (filename/metadata only).")
    return facts


def _drawing_facts(detail: dict[str, Any], analysis: SourceAnalysis,
                   repo: SourceIndexRepository | None) -> list[str]:
    facts: list[str] = []
    if analysis.sheet_number:
        facts.append(f"Sheet number: {analysis.sheet_number}")
    if analysis.sheet_title:
        facts.append(f"Sheet title: {analysis.sheet_title}")
    if analysis.discipline and analysis.discipline != "unknown":
        facts.append(f"Discipline: {analysis.discipline}")
    if analysis.issue_status:
        facts.append(f"Issue status: {analysis.issue_status}")
    if analysis.revision_number or analysis.revision_date or analysis.revision_description:
        rev = " ".join(p for p in (analysis.revision_number, analysis.revision_date) if p)
        if analysis.revision_description:
            rev = f"{rev} — {analysis.revision_description}".strip(" —")
        facts.append(f"Revision: {rev}".strip())
    facts += _referenced_sheet_facts(repo, detail["source_id"], analysis)
    if analysis.coordination_flags:
        facts.append("Coordination flags: " + ", ".join(analysis.coordination_flags[:_ADVISORY_MAX_ITEMS]))
    if analysis.datums:
        facts.append("Elevation datums: " + ", ".join(analysis.datums[:_ADVISORY_MAX_ITEMS]))
    if not detail.get("text_excerpt"):
        facts.append("Extraction unsupported — card built from filename/metadata only.")
    return facts


def _bid_facts(analysis: SourceAnalysis) -> list[str]:
    facts: list[str] = []
    if analysis.bid_package_number:
        facts.append(f"Package number: {analysis.bid_package_number}")
    if analysis.bid_package_title:
        facts.append(f"Scope / package title: {analysis.bid_package_title}")
    if analysis.inclusions:
        facts.append("Inclusions: " + "; ".join(analysis.inclusions[:_ADVISORY_MAX_ITEMS]))
    if analysis.exclusions:
        facts.append("Exclusions: " + "; ".join(analysis.exclusions[:_ADVISORY_MAX_ITEMS]))
    if analysis.trade_scope:
        facts.append("Trade scope: " + ", ".join(analysis.trade_scope[:_ADVISORY_MAX_ITEMS]))
    if analysis.procurement_signals:
        facts.append("Procurement signals: " + ", ".join(analysis.procurement_signals[:_ADVISORY_MAX_ITEMS]))
    return facts


def _spreadsheet_facts(detail: dict[str, Any], analysis: SourceAnalysis) -> list[str]:
    facts: list[str] = []
    if detail.get("sheet_count") is not None:
        facts.append(f"Sheets: {detail['sheet_count']}")
    excerpt = str(detail.get("text_excerpt") or "")
    sheet_names = [ln[4:-4].strip() for ln in excerpt.splitlines()
                   if ln.startswith("--- ") and ln.endswith(" ---")]
    if sheet_names:
        facts.append("Sheet names: " + ", ".join(sheet_names[:_ADVISORY_MAX_ITEMS]))
    low = excerpt.lower()
    hits = [term for term in _SPREADSHEET_SIGNAL_TERMS if term in low]
    if hits:
        facts.append("Detected workbook signals: " + ", ".join(hits))
    return facts


def _related_project(detail: dict[str, Any]) -> list[str]:
    """Distinguish a DETECTED project number from a RESOLVED project record (none resolved here)."""
    number = detail.get("project_number")
    if number:
        return [f"- Detected project number: {number}; no project record linked yet."]
    return ["- No project number detected; none linked yet."]


def _related_people_companies(analysis: SourceAnalysis | None) -> list[str]:
    """Detected counterparty (vendor), never implying a resolved company/person record."""
    if analysis and analysis.vendor:
        return [f"- Detected counterparty: {analysis.vendor}; no company record linked yet."]
    return ["- No people or companies detected; none linked yet."]


def _source_basis(detail: dict[str, Any], analysis: SourceAnalysis | None,
                  value: SourceValue | None, confidence: str | None,
                  config: ObsidianMcpConfig) -> list[str]:
    """Strengthened deterministic evidence of how the card was classified/produced. No full path."""
    doc_type = analysis.document_type if analysis is not None else "unknown"
    out = [f"- Card basis: {_card_basis(detail)}",
           f"- Document type: {doc_type} (deterministic — filename/metadata)"]
    if value is not None and value.reasons:
        out.append(f"- Classification reason: {', '.join(value.reasons[:6])}")
    tokens = _matched_filename_tokens(detail, config)
    if tokens:
        out.append(f"- Matched filename tokens: {', '.join(tokens)}")
    if detail.get("file_ext"):
        out.append(f"- Extension: {detail['file_ext']}")
    if (detail.get("file_ext") or "").lower() in ("xlsx", "xlsm"):
        out.append("- Spreadsheet basis: metadata + bounded cell sample (no formulas evaluated, no "
                   "macros executed).")
    if doc_type == "template_form":
        out.append("- Template/form detected from filename — treated as a blank instrument, not live data.")
    if analysis is not None:
        extracted = []
        if analysis.doc_status:
            extracted.append("status (labeled field / filename segment)")
        if analysis.amount:
            extracted.append("amount (explicit \"$\")")
        if analysis.doc_date:
            extracted.append("date (filename / labeled)")
        if extracted:
            out.append("- Deterministic extraction: " + ", ".join(extracted) + ".")
    if value is not None:
        out.append(f"- Disposition: {value.disposition.value}")
    if confidence is not None:
        out.append(f"- Confidence: {confidence} (deterministic; not model-derived)")
    out.append(f"- Source ID: `{detail['source_id']}`")
    if detail.get("content_sha256"):
        out.append(f"- SHA-256: `{detail['content_sha256']}`")
    if detail.get("indexed_at"):
        out.append(f"- Indexed at: {detail['indexed_at']}")
    return out


def _matched_filename_tokens(detail: dict[str, Any], config: ObsidianMcpConfig) -> list[str]:
    """High-priority path-signal words present in the FILENAME (safe — never the full path)."""
    name = Path(str(detail.get("rel_path") or "")).name.lower()
    if not name:
        return []
    signals = getattr(config, "source_value_high_priority_path_signals", []) or []
    return [str(s).strip() for s in signals if str(s).strip().lower() in name][:_ADVISORY_MAX_ITEMS]


def _advisory_summary(advisory: dict[str, Any] | None) -> list[str]:
    """The advisory block (clearly labelled) or an honest 'no advisory' line — never fabricated."""
    if not advisory:
        return ["- No advisory summary (deterministic card; summaries disabled)."]
    kind = advisory.get("kind")
    if kind in ("drawing", "bid_package"):
        summary = str(advisory.get("plain_english_summary") or "").strip()
        if kind == "drawing":
            list_fields = [("Scope / assembly", "scope_elements"),
                           ("Coordination items", "coordination_items"),
                           ("Submittals / shop drawings", "submittals_or_shop_drawings"),
                           ("PM follow-ups", "pm_followups")]
        else:
            list_fields = [("Scope covered", "scope_covered"),
                           ("Procurement risks", "procurement_risks"),
                           ("Bid clarifications needed", "bid_clarifications_needed"),
                           ("PM follow-ups", "pm_followups")]
    else:
        summary = str(advisory.get("summary") or "").strip()
        list_fields = [("Key points", "key_points"), ("Action items", "action_items"),
                       ("Decisions", "decisions")]
    out = ["_Advisory — model-generated, not authoritative. Verify against the source._", "",
           summary or "_(model returned no summary text)_", ""]
    for label, key in list_fields:
        out += _md_list(label, advisory.get(key) or [])
    out.append(
        f"_Model: {advisory.get('model_provider')}/{advisory.get('model_name')} · prompt "
        f"{advisory.get('prompt_version')} · generated {advisory.get('generated_at')}._")
    return out


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


_FILE_TYPE_LABELS = {
    "md": "Markdown note", "markdown": "Markdown note", "txt": "Plain-text file",
    "pdf": "PDF document", "docx": "Word document", "xlsx": "Excel workbook",
    "csv": "CSV table", "pptx": "PowerPoint deck",
}


def _render_card(config: ObsidianMcpConfig, detail: dict[str, Any], generated_at: str,
                 advisory: dict[str, Any] | None = None, *,
                 repo: SourceIndexRepository | None = None) -> str:
    """Render a source card with the canonical 11-section template body (no raw text preview).

    Section order is fixed and matches ``Templates/Source Cards/source-card-template.md``: Source
    Summary, Why This Matters, PM Review Cues, Key Facts, Related Project, Related People / Companies,
    Related Decisions, Related Meetings, Source Basis, Advisory Summary, Follow-Up. Type-specific
    deterministic detail is folded into Key Facts; the Related sections distinguish DETECTED facts
    from RESOLVED records (no relationship is implied unless one was actually resolved).
    """
    display = Path(detail["rel_path"]).name if detail.get("rel_path") else str(detail.get("domain_ref_id"))
    # Deterministic construction analysis (file sources only; sensitive sources have no excerpt).
    analysis = source_analyzers.from_detail(detail) if detail.get("rel_path") else None
    # Thread the PM-value disposition + a deterministic confidence/domain/review_status into the card.
    value = classify_source_value(detail, config) if detail.get("rel_path") else None
    domain = _domain_for(detail)
    confidence = derive_confidence(value) if value is not None else None
    needs_review = confidence == "low" or (
        analysis is not None and analysis.document_type in _AMBIGUOUS_DOC_TYPES)
    review_status = "needs_review" if needs_review else "unreviewed"
    guidance = _pm_guidance(analysis.document_type if analysis is not None else None)

    parts = [_frontmatter(detail, generated_at, advisory, analysis, value=value, domain=domain,
                          review_status=review_status, confidence=confidence),
             "", f"# Source Card: {display}", ""]
    parts += ["## Source Summary", *_source_summary_lines(detail, analysis), ""]
    parts += ["## Why This Matters", *[f"- {w}" for w in guidance["why"]], ""]
    parts += ["## PM Review Cues",
              *[f"- {c}" for c in _review_cues(detail, analysis, guidance, review_status)], ""]
    parts += ["## Key Facts", *[f"- {f}" for f in _key_facts(detail, analysis, repo)], ""]
    parts += ["## Related Project", *_related_project(detail), ""]
    parts += ["## Related People / Companies", *_related_people_companies(analysis), ""]
    parts += ["## Related Decisions", "- No related decisions linked yet.", ""]
    parts += ["## Related Meetings", "- No related meetings linked yet.", ""]
    parts += ["## Source Basis", *_source_basis(detail, analysis, value, confidence, config), ""]
    parts += ["## Advisory Summary", *_advisory_summary(advisory), ""]
    parts += ["## Follow-Up", *[f"- [ ] {f}" for f in guidance["followup"]], ""]
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
    if detail.get("rel_path") and is_deferred_source_path(str(detail["rel_path"]), config):
        # Deferred business record: skip auto-summary (clean reason, no model call). Distinct from
        # excluded — deferred sources stay indexed/searchable and may be carded manually.
        return {"summarized": False, "reason": "deferred_path",
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
