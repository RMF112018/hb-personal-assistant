"""PM-value disposition policy for Source Intelligence.

Pure, deterministic classifier that routes each source into one disposition so automatic card
generation prefers high-value construction PM/control artifacts and suppresses placeholders,
screenshots, system/test files, and broad business-record folders. NO LLM, NO I/O, NO new deps.

Self-contained path/ext matching (does not import ``source_indexer`` to avoid an import cycle);
segment-equality mirrors ``is_excluded_source_path``/``is_deferred_source_path`` exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .config import ObsidianMcpConfig
from .source_skip_codes import (
    DEFERRED_PATH,
    EXCLUDED_PATH,
    METADATA_ONLY_NO_AUTO_CARD,
    UNSUPPORTED_FILE_TYPE,
)


class SourceValueDisposition(str, Enum):
    AUTO_CARD_HIGH = "auto_card_high"
    AUTO_CARD_NORMAL = "auto_card_normal"
    METADATA_ONLY = "metadata_only"
    DEFERRED = "deferred"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"


_D = SourceValueDisposition
# Lower priority_score == preferred earlier in a drain.
_DISP_RANK: dict[SourceValueDisposition, int] = {
    _D.AUTO_CARD_HIGH: 0, _D.AUTO_CARD_NORMAL: 1, _D.METADATA_ONLY: 2,
    _D.DEFERRED: 3, _D.UNSUPPORTED: 4, _D.EXCLUDED: 5,
}

# document_type -> disposition mapping (the analyzer is the single source of types).
HIGH_DOCUMENT_TYPES = frozenset({
    "architectural_drawing", "structural_drawing", "mep_drawing", "civil_drawing", "drawing",
    "bid_package", "scope_of_work", "rfi", "submittal", "meeting_minutes", "schedule", "specification",
    "cost_document", "change_order", "potential_change_order", "pay_application",
    "contract", "subcontract", "purchase_order", "daily_log", "manpower_log",
    "punch_list", "punchlist",  # punch_list canonical; punchlist kept for backward compatibility
    "closeout", "warranty", "operations_maintenance",
    "cost_report", "project_controls", "staffing_report",
    "safety", "quality", "inspection",
})
# NORMAL also covers unknown-but-real project documents (general_pdf/general_document): they still
# get a card, just not prioritized ahead of recognized PM/control artifacts. METADATA_ONLY is reserved
# for generic spreadsheets/CSV (no high-value class) — images/placeholders are UNSUPPORTED.
NORMAL_DOCUMENT_TYPES = frozenset({
    "presentation", "marketing", "site_map", "general_pdf", "general_document",
})
# Generic/reference workbook classes the analyzer did NOT promote to a high-value class. These must
# never be path-signal-promoted to auto_card_high (Phase 10A internal-consistency guard): a card that
# reports "no high-value workbook class detected" cannot also sit at auto_card_high.
_NO_AUTO_HIGH_TYPES = frozenset({
    "spreadsheet", "communications_matrix", "coordination_matrix", "equipment_log",
    "reference_document",
})


@dataclass(frozen=True)
class SourceValue:
    disposition: SourceValueDisposition
    priority_score: int
    bucket: str
    allow_auto_card: bool
    allow_auto_summary: bool
    allow_metadata_index: bool
    skip_code: str | None = None
    reasons: list[str] = field(default_factory=list)


def _ext_norm(file_ext: Any) -> str:
    """Canonical extension: strip a leading dot + lowercase (so 'PNG'/'.png'/'png' all match)."""
    return str(file_ext or "").strip().lower().lstrip(".")


def _path_has_segment(rel_path: str, parts: Any) -> bool:
    """STRICT segment-equality (folder names): no substring matching."""
    part_set = {str(p).strip().replace("\\", "/").strip("/").lower() for p in (parts or []) if str(p).strip()}
    if not part_set:
        return False
    segments = [s for s in str(rel_path).replace("\\", "/").lower().split("/") if s]
    return any(s in part_set for s in segments)


def _path_has_signal(rel_path: str, signals: Any) -> bool:
    """SUBSTRING/keyword match (promotions only) — e.g. 'pay app' inside '03 Pay Applications'."""
    low = str(rel_path).replace("\\", "/").lower()
    return any(str(sig).strip().lower() in low for sig in (signals or []) if str(sig).strip())


def _build(disposition: SourceValueDisposition, *, reasons: list[str], config: ObsidianMcpConfig,
           skip_code: str | None, allow_metadata_index: bool) -> SourceValue:
    allow_card = disposition in (_D.AUTO_CARD_HIGH, _D.AUTO_CARD_NORMAL) or (
        disposition is _D.METADATA_ONLY
        and bool(getattr(config, "source_card_auto_metadata_only_enabled", False))
    )
    allow_summary = allow_card and disposition in (_D.AUTO_CARD_HIGH, _D.AUTO_CARD_NORMAL)
    code = skip_code
    if code is None and not allow_card and disposition is _D.METADATA_ONLY:
        code = METADATA_ONLY_NO_AUTO_CARD
    return SourceValue(
        disposition=disposition,
        priority_score=_DISP_RANK[disposition] * 100,
        bucket=disposition.value,
        allow_auto_card=allow_card,
        allow_auto_summary=allow_summary,
        allow_metadata_index=allow_metadata_index,
        skip_code=code,
        reasons=reasons,
    )


def derive_confidence(value: SourceValue) -> str:
    """Deterministic, explainable confidence label (high/medium/low) for a source card.

    HIGH disposition driven by the document_type itself → ``high``; a HIGH reached only via a
    filename/path signal promotion → ``medium`` (weaker evidence); NORMAL → ``medium``; everything
    else (metadata-only/deferred/unsupported) → ``low``. Purely a function of disposition + reasons.
    """
    promoted = any(r in ("high_path_signal", "normal_path_signal") for r in value.reasons)
    if value.disposition is _D.AUTO_CARD_HIGH:
        return "medium" if promoted else "high"
    if value.disposition is _D.AUTO_CARD_NORMAL:
        return "medium"
    return "low"


def classify_source_value(detail: dict[str, Any], config: ObsidianMcpConfig) -> SourceValue:
    """Classify an indexed source ``detail`` into a PM-value disposition (deterministic).

    Order: excluded (hard, no index) → unsupported ext (no index) → deferred (indexed, no auto-card)
    → document-type mapping (high/normal/metadata) → generic-spreadsheet metadata gate → path-signal
    promotions (upgrade only). Never downgrades a document-type HIGH.
    """
    rel = str(detail.get("rel_path") or "")
    ext = _ext_norm(detail.get("file_ext"))

    if rel and _path_has_segment(rel, getattr(config, "source_index_excluded_path_parts", [])):
        return _build(_D.EXCLUDED, reasons=["excluded_path_segment"], config=config,
                      skip_code=EXCLUDED_PATH, allow_metadata_index=False)
    unsupported = {_ext_norm(e) for e in (getattr(config, "source_index_unsupported_file_types", []) or [])}
    if ext and ext in unsupported:
        return _build(_D.UNSUPPORTED, reasons=[f"unsupported_ext:{ext}"], config=config,
                      skip_code=UNSUPPORTED_FILE_TYPE, allow_metadata_index=False)
    if rel and _path_has_segment(rel, getattr(config, "source_index_deferred_path_parts", [])):
        return _build(_D.DEFERRED, reasons=["deferred_path_segment"], config=config,
                      skip_code=DEFERRED_PATH, allow_metadata_index=True)

    from . import source_analyzers  # lazy: pure module, avoids any import-order surprise
    document_type = source_analyzers.from_detail(detail).document_type
    reasons = [f"doc_type:{document_type}"]
    # Template / blank-form documents are never auto-carded and never path-signal-promoted (a template
    # filed under a "Change Orders" folder must not be promoted to high). Stays metadata_only.
    if document_type == "template_form":
        return _build(_D.METADATA_ONLY, reasons=reasons + ["template_form_no_auto_card"],
                      config=config, skip_code=None, allow_metadata_index=True)
    if document_type in HIGH_DOCUMENT_TYPES:
        disposition = _D.AUTO_CARD_HIGH
    elif document_type in NORMAL_DOCUMENT_TYPES:
        disposition = _D.AUTO_CARD_NORMAL
    else:
        disposition = _D.METADATA_ONLY

    # Generic spreadsheets/CSV that the analyzer did not promote stay metadata_only.
    metadata_exts = {_ext_norm(e) for e in (getattr(config, "source_index_metadata_only_file_types", []) or [])}
    if ext in metadata_exts and disposition is not _D.AUTO_CARD_HIGH:
        disposition = _D.METADATA_ONLY
        reasons.append(f"metadata_only_ext:{ext}")

    # Path-signal promotions (upgrade only — never demote a HIGH). Internal-consistency guard
    # (Phase 10A): a generic/reference workbook (no high-value class detected) is NEVER promoted to
    # high by a folder path signal — else a card would say "no high-value class" yet be auto_card_high.
    if (disposition is not _D.AUTO_CARD_HIGH and document_type not in _NO_AUTO_HIGH_TYPES
            and _path_has_signal(
                rel, getattr(config, "source_value_high_priority_path_signals", []))):
        disposition = _D.AUTO_CARD_HIGH
        reasons.append("high_path_signal")
    elif disposition is _D.METADATA_ONLY and _path_has_signal(
        rel, getattr(config, "source_value_normal_priority_path_signals", [])
    ):
        disposition = _D.AUTO_CARD_NORMAL
        reasons.append("normal_path_signal")

    return _build(disposition, reasons=reasons, config=config, skip_code=None,
                  allow_metadata_index=True)


def classify_path_disposition(rel_path: str, file_ext: str | None, config: ObsidianMcpConfig) -> SourceValueDisposition:
    """Coarse path/ext-only disposition for queued events not yet indexed (no document_type).

    Used by the ``queued_by_disposition`` diagnostic; high/normal are filename-signal-based only.
    """
    ext = _ext_norm(file_ext)
    if rel_path and _path_has_segment(rel_path, getattr(config, "source_index_excluded_path_parts", [])):
        return _D.EXCLUDED
    unsupported = {_ext_norm(e) for e in (getattr(config, "source_index_unsupported_file_types", []) or [])}
    if ext and ext in unsupported:
        return _D.UNSUPPORTED
    if rel_path and _path_has_segment(rel_path, getattr(config, "source_index_deferred_path_parts", [])):
        return _D.DEFERRED
    if _path_has_signal(rel_path, getattr(config, "source_value_high_priority_path_signals", [])):
        return _D.AUTO_CARD_HIGH
    if _path_has_signal(rel_path, getattr(config, "source_value_normal_priority_path_signals", [])):
        return _D.AUTO_CARD_NORMAL
    metadata_exts = {_ext_norm(e) for e in (getattr(config, "source_index_metadata_only_file_types", []) or [])}
    if ext in metadata_exts:
        return _D.METADATA_ONLY
    return _D.AUTO_CARD_NORMAL  # unknown-but-supported: coarse default (refined at index time)
