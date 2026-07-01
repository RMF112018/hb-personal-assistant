"""Phase 10K: safe, bounded, reversible source-card classification repair (managed-block preserving).

Given a generated source card + its indexed ``detail``, plan the deterministic classifier repair and
produce a new card body that changes ONLY:
  - frontmatter ``document_type``;
  - the ``source/type/*`` frontmatter tag;
  - the Source Summary / Source Basis "Document type:" line and the Source Basis classification reason;
  - the Why This Matters and PM Review Cues section bodies (regenerated from the deterministic
    ``_PM_GUIDANCE`` for the repaired type, via the real renderer helpers).

Every managed block (``hb-local-summary``, ``hb-project-identity``, ``gc-graph-links``, ``hb-email*``,
and any unknown ``<!-- … -->`` block) is preserved byte-for-byte: section-body edits refuse if a marker
is present, and line-level edits stop at the first marker. Source ID/SHA/path/timestamps and all other
manual content are never touched. Fail-safe: any missing/ambiguous section aborts the whole plan (no
partial write). Idempotent: re-running on an already-repaired card is a no-op.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import source_note_graph as ng
from .source_analyzers import from_detail
from .source_document_classifier import classify_source_document
from .source_notes import _pm_guidance, _review_cues

_FENCE = "---"
_MARKER_RE = re.compile(r"<!--")
_DOCTYPE_LINE_RE = re.compile(r"^- Document type: .*\(deterministic")
_REASON_LINE_RE = re.compile(r"^- Classification reason: ")


# --------------------------------------------------------------------------- frontmatter helpers
def _frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    if not lines or lines[0].strip() != _FENCE:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FENCE:
            return 0, i
    return None


def _frontmatter_value(card_text: str, key: str) -> str | None:
    lines = card_text.splitlines()
    b = _frontmatter_bounds(lines)
    if b is None:
        return None
    pat = re.compile(rf'^{re.escape(key)}:\s*"?(.*?)"?\s*$')
    for i in range(b[0] + 1, b[1]):
        m = pat.match(lines[i])
        if m:
            return m.group(1).strip()
    return None


def set_frontmatter_scalar(card_text: str, key: str, value: str) -> tuple[str | None, str]:
    """Replace a scalar frontmatter value, preserving quote style and everything else byte-for-byte."""
    lines = card_text.splitlines(keepends=True)
    b = _frontmatter_bounds([ln.rstrip("\n") for ln in lines])
    if b is None:
        return None, "no_frontmatter"
    pat = re.compile(rf'^{re.escape(key)}:\s*(.*?)\s*$')
    for i in range(b[0] + 1, b[1]):
        m = pat.match(lines[i].rstrip("\n"))
        if m:
            old = m.group(1)
            quoted = old.startswith('"') and old.endswith('"')
            newv = f'"{value}"' if quoted else value
            nl = "\n" if lines[i].endswith("\n") else ""
            lines[i] = f"{key}: {newv}{nl}"
            return "".join(lines), "ok"
    return None, "key_not_found"


def swap_source_type_tag(card_text: str, new_slug: str) -> tuple[str | None, str]:
    """Remove every existing ``source/type/*`` frontmatter tag and add ``source/type/{new_slug}``."""
    ok, tags, _f, _l = ng.parse_frontmatter_tags(card_text)
    if not ok:
        return None, "frontmatter_not_block_style"
    existing_type_tags = [t for t in tags if t.startswith("source/type/")]
    if existing_type_tags == [f"source/type/{new_slug}"]:
        return card_text, "no_change"
    txt = card_text
    if existing_type_tags:
        txt, r = ng.remove_frontmatter_tags(txt, existing_type_tags)
        if txt is None:
            return None, r
    txt, r = ng.apply_tags(txt, [f"source/type/{new_slug}"])
    if txt is None:
        return None, r
    return txt, "ok"


# --------------------------------------------------------------------------- section helpers
def _section_span(lines: list[str], heading: str) -> tuple[int, int, int] | None:
    """Return (heading_idx, body_start, body_end_exclusive) for a top-level ``## `` heading."""
    h = next((i for i, ln in enumerate(lines) if ln.strip() == heading), -1)
    if h == -1:
        return None
    end = next((i for i in range(h + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return h, h + 1, end


def replace_section_body(card_text: str, heading: str,
                         new_body_lines: list[str]) -> tuple[str | None, str]:
    """Replace a section body (deterministic prose only). Refuse if a managed marker is inside."""
    lines = card_text.splitlines()
    span = _section_span(lines, heading)
    if span is None:
        return None, "section_not_found"
    _h, bstart, bend = span
    body = lines[bstart:bend]
    if any(_MARKER_RE.search(ln) for ln in body):
        return None, "managed_marker_in_section"
    trailing = 0
    j = bend - 1
    while j >= bstart and lines[j].strip() == "":
        trailing += 1
        j -= 1
    new = lines[:bstart] + list(new_body_lines) + [""] * trailing + lines[bend:]
    tail = "\n" if card_text.endswith("\n") else ""
    return "\n".join(new) + tail, "ok"


def replace_doctype_line(card_text: str, heading: str, new_type: str) -> tuple[str | None, str]:
    """Line-level replace of the ``- Document type: …`` line within a section, stopping at markers."""
    lines = card_text.splitlines()
    span = _section_span(lines, heading)
    if span is None:
        return None, "section_not_found"
    _h, bstart, bend = span
    for i in range(bstart, bend):
        if _MARKER_RE.search(lines[i]):
            break
        if _DOCTYPE_LINE_RE.match(lines[i]):
            lines[i] = f"- Document type: {new_type} (deterministic — filename/metadata)"
            tail = "\n" if card_text.endswith("\n") else ""
            return "\n".join(lines) + tail, "ok"
    return None, "doctype_line_not_found"


def set_source_basis_classification(card_text: str, new_type: str,
                                    reason_text: str) -> tuple[str | None, str]:
    """Update the Source Basis ``Document type`` + ``Classification reason`` lines (marker-safe)."""
    lines = card_text.splitlines()
    span = _section_span(lines, "## Source Basis")
    if span is None:
        return None, "source_basis_not_found"
    _h, bstart, bend = span
    changed_type = changed_reason = False
    for i in range(bstart, bend):
        if _MARKER_RE.search(lines[i]):
            break  # never cross an hb-email* marker inside Source Basis
        if _DOCTYPE_LINE_RE.match(lines[i]):
            lines[i] = f"- Document type: {new_type} (deterministic — filename/metadata)"
            changed_type = True
        elif _REASON_LINE_RE.match(lines[i]):
            lines[i] = f"- Classification reason: {reason_text}"
            changed_reason = True
    if not (changed_type and changed_reason):
        return None, "source_basis_lines_not_found"
    tail = "\n" if card_text.endswith("\n") else ""
    return "\n".join(lines) + tail, "ok"


# --------------------------------------------------------------------------- summary consistency
def _summary_block(card_text: str) -> tuple[str | None, str]:
    """Return (status, body) for the hb-local-summary block; status None if the block is absent."""
    lines = card_text.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip().startswith("<!-- hb-local-summary:start")), None)
    if start is None:
        return None, ""
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip().startswith("<!-- hb-local-summary:end")), len(lines))
    m = re.search(r'status="([^"]*)"', lines[start])
    return (m.group(1) if m else ""), "\n".join(lines[start + 1:end])


def summary_asserts_conflicting_type(summary_body: str, new_type: str) -> bool:
    """True when a generated summary still asserts the OLD document nature (mirrors 10J conflict gates)."""
    low = (summary_body or "").lower()
    if new_type == "value_analysis":
        return bool(re.search(r"warrant", low)) and not re.search(
            r"value[- ]?analysis|value engineering|\bva\b|tracking log|value tracking", low)
    if new_type == "specification_template":
        return bool(re.search(r"project[- ]specific submittal|is a submittal|project submittal", low)) \
            and not re.search(r"generic|template", low)
    if new_type == "clarification_memo":
        return bool(re.search(r"scope of work", low)) and not re.search(
            r"clarification|question|open item|\bmemo\b", low)
    return False


# --------------------------------------------------------------------------- planner
@dataclass(frozen=True)
class CardRepairPlan:
    action: str  # "repair" | "noop" | "review" | "skip"
    from_type: str
    to_type: str
    confidence: str
    review_required: bool
    classification_conflict: bool
    signals: tuple[str, ...]
    skip_reason: str | None
    sections_changed: tuple[str, ...]
    new_text: str | None


def _skip(existing: str, to_type: str, c, reason: str) -> CardRepairPlan:
    return CardRepairPlan("skip", existing, to_type, c.confidence, c.review_required,
                          c.classification_conflict, c.classification_signals, reason, (), None)


def plan_card_classification_repair(card_text: str, detail: dict) -> CardRepairPlan:
    """Plan a safe repair for one card. Returns a CardRepairPlan; ``new_text`` set only for "repair"."""
    existing = str(_frontmatter_value(card_text, "document_type") or "").strip()
    rel = str(detail.get("rel_path") or "")
    c = classify_source_document(
        filename=rel.rsplit("/", 1)[-1], source_path=rel, extension=str(detail.get("file_ext") or ""),
        extracted_text_excerpt=str(detail.get("text_excerpt") or ""), existing_document_type=existing)
    new_type = c.document_type

    if new_type == existing:
        action = "review" if c.review_required else "noop"
        return CardRepairPlan(action, existing, existing, c.confidence, c.review_required,
                              c.classification_conflict, c.classification_signals, None, (), None)

    # Amendment 2: never leave a card whose preserved generated summary still asserts the old type.
    status, body = _summary_block(card_text)
    if status == "generated" and summary_asserts_conflicting_type(body, new_type):
        return _skip(existing, new_type, c, "summary_refresh_required")

    analysis = from_detail(detail)  # repaired type flows through the deterministic renderer helpers
    guidance = _pm_guidance(new_type)
    review_status = str(_frontmatter_value(card_text, "review_status") or "unreviewed")
    new_slug = ng._DOCTYPE_CONTENT.get(new_type, "unknown")
    signals_txt = ", ".join(c.classification_signals) or "deterministic"
    reason_text = f"doc_type:{new_type} (Phase 10K repair from '{existing}'; signals: {signals_txt})"

    txt = card_text
    steps = [
        ("frontmatter.document_type", lambda t: set_frontmatter_scalar(t, "document_type", new_type)),
        ("frontmatter.source_type_tag", lambda t: swap_source_type_tag(t, new_slug)),
        ("Source Summary", lambda t: replace_doctype_line(t, "## Source Summary", new_type)),
        ("Why This Matters", lambda t: replace_section_body(
            t, "## Why This Matters", [f"- {w}" for w in guidance["why"]])),
        ("PM Review Cues", lambda t: replace_section_body(
            t, "## PM Review Cues",
            [f"- {x}" for x in _review_cues(detail, analysis, guidance, review_status)])),
        ("Source Basis", lambda t: set_source_basis_classification(t, new_type, reason_text)),
    ]
    changed: list[str] = []
    for label, fn in steps:
        nxt, reason = fn(txt)
        if nxt is None:
            return _skip(existing, new_type, c, f"{label}:{reason}")  # fail-safe, no partial write
        if nxt != txt:
            changed.append(label)
        txt = nxt

    if txt == card_text:
        return CardRepairPlan("noop", existing, existing, c.confidence, c.review_required,
                              c.classification_conflict, c.classification_signals, None, (), None)
    return CardRepairPlan("repair", existing, new_type, c.confidence, c.review_required,
                          c.classification_conflict, c.classification_signals, None,
                          tuple(changed), txt)
