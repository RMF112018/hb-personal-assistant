"""Phase 10K: deterministic source-document classifier-repair + provenance (pure, dependency-light).

Phase 10J *surfaced and counted* classifier conflicts but never repaired them. This module is the
deterministic repair layer: given a source document's filename/path/extension/extracted-text, it
decides whether the upstream ``document_type`` should be corrected to one of three known-misclassified
families, and produces PM-safe provenance (confidence / signals / conflict / reason / review-required).

Design constraints (Phase 10K):
- **Pure and dependency-light** — only ``re``/stdlib, no Ollama, no DB, no file reads. Safe to import
  from the low-level classifier ``source_analyzers`` without pulling heavy deps.
- **Guarded to three families only** — value-analysis logs, generic specification templates, and
  clarification/question memos. It may only overwrite an existing type that is a known *conflict* for
  the detected family or a *weak/ambiguous* base type; it never touches an unrelated confident type.
- **Strong multi-signal evidence required** — filename/title AND extracted-text evidence (never path or
  title alone). Thin/ambiguous documents are left unchanged and marked ``review_required``.

The family-signal helpers (``_title_signal``, ``_FAMILY_CONFLICTS``, ``_FAMILY_REQUIRED``,
``detect_classification_conflict``) were introduced in Phase 10J's ``source_local_summary`` and are
hosted here as the single source of truth; ``source_local_summary`` re-imports them unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Phase 10J family-signal detection (moved here; source_local_summary re-imports) --------------
_SPEC_SECTION_RE = re.compile(r"\b\d\d[\s-]\d\d[\s-]\d\d\b")  # e.g. 02 87 13 / 02-87-13


def _title_signal(title: str, excerpt: str) -> str | None:
    """Deterministic document-family signal from the title + excerpt header (never body-only guess)."""
    ttok = set(re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).split())
    head = (str(title or "") + "\n" + str(excerpt or "")[:1200]).lower()
    hnorm = re.sub(r"[^a-z0-9]+", " ", head)
    if ("va" in ttok and ("log" in ttok or "tracking" in ttok)) or "value analysis" in hnorm \
            or "value engineering" in hnorm:
        return "value_analysis_log"
    if _SPEC_SECTION_RE.search(head) or "masterworks" in hnorm or "master works" in hnorm \
            or "specification" in hnorm or "part 1 general" in hnorm or "part 2 products" in hnorm:
        return "specification_generic"
    if re.search(r"clarification|open items|open questions|memorandum|preconstruction question", hnorm) \
            or " memo " in f" {hnorm} " or head.count("?") >= 2:
        return "memo_questions"
    if "transmittal" in hnorm:
        return "transmittal"
    if "warranty" in hnorm or "warrant" in ttok:
        return "warranty"
    if "tracking" in hnorm or "log" in ttok:
        return "tracker"
    return None


# document_type values that CONTRADICT a detected family (a *hard* conflict to repair).
_FAMILY_CONFLICTS = {
    "value_analysis_log": {"warranty", "contract", "submittal"},
    "specification_generic": {"submittal", "scope_of_work", "warranty", "contract"},
    "memo_questions": {"scope_of_work", "contract", "submittal", "warranty"},
    "transmittal": {"scope_of_work", "contract"},
}
# For a detected family, EACH required signal group must match (>=1 per group) in the excerpt.
_FAMILY_REQUIRED: dict[str, list[str]] = {
    "value_analysis_log": [r"value[- ]?analysis|value engineering|\bva\b|tracking log|value tracking",
                           r"line[- ]?item|status|value|alternate"],
    "specification_generic": [r"generic|template|specification|spec package|standard|master ?works",
                              r"clean|kill|coat|moisture|iicrc|s\s?520|submittal|sds|voc|product|"
                              r"manufacturer|remediation"],
    "memo_questions": [r"clarification|question|open item|preconstruction|unresolved|"
                       r"to be (confirmed|determined)|\bmemo\b"],
}


def detect_classification_conflict(document_type: str | None, title: str, excerpt: str) -> str | None:
    """Return the true document family when title/content contradict document_type, else None."""
    fam = _title_signal(title, excerpt)
    if fam and str(document_type or "").lower() in _FAMILY_CONFLICTS.get(fam, set()):
        return fam
    return None


# =================================================================================================
# Phase 10K classifier-repair service
# =================================================================================================

# The three families this phase may repair, and the canonical document_type each maps to.
_FAMILY_TO_TYPE: dict[str, str] = {
    "value_analysis_log": "value_analysis",
    "specification_generic": "specification_template",
    "memo_questions": "clarification_memo",
}
# The canonical repaired types, for downstream consistency checks / tests.
REPAIR_TARGET_TYPES: frozenset[str] = frozenset(_FAMILY_TO_TYPE.values())

# Weak / ambiguous base types a strong family signal is allowed to refine (in addition to the
# family's hard-conflict set). A confident, unrelated type is never overwritten.
_WEAK_TYPES: frozenset[str] = frozenset({
    "", "unknown", "general_pdf", "general_document", "reference_document", "template_form",
    "spreadsheet", "cost_document", "specification",
})

# Excerpt-evidence sub-signals (deterministic tokens only — never raw paths/excerpt text).
_VA_TEXT_SIGNALS: list[tuple[str, str]] = [
    (r"value[- ]?analysis|value engineering", "text:value-analysis"),
    (r"tracking log|value tracking|\btracking\b", "text:tracking"),
    (r"line[- ]?item", "text:line-items"),
    (r"\bstatus\b", "text:status"),
    (r"\bvalue\b|\bamount\b|\balternate\b", "text:value-column"),
    (r"#ref", "text:ref-error"),
]
_SPEC_GENERIC_SIGNALS: list[tuple[str, str]] = [
    (r"generic|template|spec package", "text:generic-template"),
    (r"master ?works", "text:masterworks"),
    (r"specifier|editing note|hidden text|\bretain\b|\bdelete\b|\[?specifier", "text:specifier-notes"),
    (r"part 1 general|part 2 products|part 3 execution", "text:spec-structure"),
]
_MEMO_TEXT_SIGNALS: list[tuple[str, str]] = [
    (r"clarification", "text:clarification"),
    (r"\bquestion", "text:question"),
    (r"open item|open question|unresolved|to be (confirmed|determined)", "text:open-items"),
    (r"preconstruction question|\bmemo\b|memorandum", "text:memo"),
]


@dataclass(frozen=True)
class SourceDocumentClassification:
    """PM-safe classifier output. ``classification_signals`` holds deterministic tokens only."""

    document_type: str
    confidence: str  # "high" | "medium" | "low"
    classification_reason: str
    classification_signals: tuple[str, ...]
    classification_conflict: bool
    conflict_reason: str | None
    review_required: bool


@dataclass(frozen=True)
class ClassificationRepairDecision:
    repaired: bool
    from_type: str
    to_type: str
    confidence: str
    reason: str
    review_required: bool
    signals: tuple[str, ...] = field(default_factory=tuple)


def _count_hits(patterns: list[tuple[str, str]], text: str) -> list[str]:
    low = str(text or "").lower()
    return [tok for pat, tok in patterns if re.search(pat, low)]


def _family_strength(filename: str, excerpt: str) -> tuple[str | None, list[str], bool]:
    """Detect the repair family and whether STRONG multi-signal evidence supports it.

    Returns ``(family, signals, strong)``. ``strong`` requires filename/title AND excerpt evidence for
    value-analysis and specification-template; clarification-memo requires genuine excerpt
    question/open-item structure (a short filename alone is never enough).
    """
    fam = _title_signal(filename, excerpt)
    if fam not in _FAMILY_TO_TYPE:
        return fam, [], False
    excerpt = str(excerpt or "")
    signals: list[str] = []
    strong = False

    if fam == "value_analysis_log":
        title_only = _title_signal(filename, "") == "value_analysis_log"
        if title_only:
            signals.append("title:va-log")
        text_hits = _count_hits(_VA_TEXT_SIGNALS, excerpt)
        signals += text_hits
        # filename/title signal AND >=2 distinct excerpt signals (tracking/status/value/#REF/etc.)
        strong = title_only and len(text_hits) >= 2

    elif fam == "specification_generic":
        head = (filename + "\n" + excerpt[:1200]).lower()
        if _SPEC_SECTION_RE.search(head):
            signals.append("title:spec-section")
        if re.search(r"master ?works", head):
            signals.append("title:masterworks")
        if "specification" in head:
            signals.append("title:specification")
        generic_hits = _count_hits(_SPEC_GENERIC_SIGNALS, excerpt)
        signals += generic_hits
        # A section/spec/masterworks signal PLUS excerpt evidence of GENERIC/TEMPLATE nature — this is
        # the discriminator vs a real project submittal (which lacks specifier/template structure).
        has_domain = bool(signals) and any(s.startswith("title:") for s in signals)
        strong = has_domain and len(generic_hits) >= 1

    elif fam == "memo_questions":
        qmarks = excerpt.count("?")
        text_hits = _count_hits(_MEMO_TEXT_SIGNALS, excerpt)
        signals += text_hits
        if qmarks >= 2:
            signals.append("text:question-marks")
        # Genuine question/open-item structure — not merely a short document with a hint word.
        strong = qmarks >= 2 or len(text_hits) >= 2

    return fam, signals, strong


def _repairable_existing(fam: str) -> frozenset[str]:
    return frozenset(_FAMILY_CONFLICTS.get(fam, set())) | _WEAK_TYPES


def _repair_reason(fam: str, proposed: str, existing: str, hard: bool) -> str:
    family_label = {
        "value_analysis_log": "a value-analysis / VE tracking log",
        "specification_generic": "a generic specification template",
        "memo_questions": "a clarification / open-questions memo",
    }.get(fam, "a known document family")
    if hard:
        return (f"Filename and extracted text identify {family_label}; classifier hint "
                f"'{existing}' is contradicted by the source signals — repaired to '{proposed}'.")
    return (f"Filename and extracted text identify {family_label}; refined the weak base type "
            f"'{existing or 'unknown'}' to '{proposed}'.")


def classify_source_document(*, filename: str, source_path: str, extension: str,
                             extracted_text_excerpt: str,
                             existing_document_type: str | None = None,
                             ) -> SourceDocumentClassification:
    """Deterministic, explainable classification with guarded three-family repair.

    ``source_path``/``extension`` are accepted for signature completeness but path is deliberately NOT
    authoritative (amendment 5: never repair from path/title alone). Returns the existing type unchanged
    when no strong repair family is detected.
    """
    existing = str(existing_document_type or "").strip().lower()
    fam, signals, strong = _family_strength(filename, extracted_text_excerpt)
    sig = tuple(signals)

    if fam in _FAMILY_TO_TYPE:
        proposed = _FAMILY_TO_TYPE[fam]
        if existing == proposed:
            return SourceDocumentClassification(
                proposed, "high", f"Already classified as '{proposed}'.", sig,
                classification_conflict=False, conflict_reason=None, review_required=False)
        if strong and existing in _repairable_existing(fam):
            hard = existing in _FAMILY_CONFLICTS.get(fam, set())
            reason = _repair_reason(fam, proposed, existing, hard)
            return SourceDocumentClassification(
                proposed, "high" if hard else "medium", reason, sig,
                classification_conflict=hard,
                conflict_reason=reason if hard else None, review_required=False)
        # Family hinted but evidence is thin, OR existing is a confident unrelated type — keep it and
        # flag for human review rather than guess.
        reason = ("Family signal present but excerpt evidence is thin — left unchanged for review."
                  if not strong else
                  f"Family signal present; existing type '{existing or 'unknown'}' kept (not a known "
                  f"conflict) — flagged for review.")
        return SourceDocumentClassification(
            existing or "unknown", "low", reason, sig,
            classification_conflict=False, conflict_reason=None, review_required=True)

    # No repairable family signal — keep the existing deterministic type verbatim.
    return SourceDocumentClassification(
        existing or "unknown", "high" if existing else "low",
        "No repair-family signal detected; existing classification retained.", sig,
        classification_conflict=False, conflict_reason=None, review_required=False)


def detect_classification_repair(*, existing_document_type: str, proposed_document_type: str,
                                 signals: list[str] | None = None) -> ClassificationRepairDecision:
    """Pure decision object over an (existing, proposed) type pair — used by the repair planner/tests."""
    ex = str(existing_document_type or "").strip().lower()
    pr = str(proposed_document_type or "").strip().lower()
    sig = tuple(signals or ())
    if not pr or pr == ex:
        return ClassificationRepairDecision(False, ex, ex, "high", "No change.", False, sig)
    fam = next((f for f, t in _FAMILY_TO_TYPE.items() if t == pr), None)
    hard = bool(fam) and ex in _FAMILY_CONFLICTS.get(fam or "", set())
    reason = _repair_reason(fam or "", pr, ex, hard)
    return ClassificationRepairDecision(True, ex, pr, "high" if hard else "medium", reason, False, sig)


def repair_document_type(rel_path: str, extension: str, text_excerpt: str,
                         document_type: str) -> str:
    """Guarded adapter for the upstream classifier (``source_analyzers.from_detail``).

    Returns a corrected ``document_type`` ONLY when a strong three-family signal repairs a
    conflicting/weak base type; otherwise returns ``document_type`` unchanged. Safe with empty text
    (sensitive sources with no excerpt never repair).
    """
    filename = rel_path.rsplit("/", 1)[-1]
    result = classify_source_document(
        filename=filename, source_path=rel_path, extension=extension,
        extracted_text_excerpt=text_excerpt, existing_document_type=document_type)
    return result.document_type
