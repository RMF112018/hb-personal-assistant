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


# ===========================================================================================
# Phase 10K.1 — post-repair polish (Follow-Up + stale related/review tags only)
# ===========================================================================================
# The classifier repair (above) corrects document_type / source-type tag / Why / Cues / Source Basis
# but deliberately does NOT touch the ``## Follow-Up`` section or the topical ``related/*`` tags, so a
# repaired card can still carry pre-repair Follow-Up prose and a related tag justified only by the old
# type. This polish regenerates Follow-Up from the (already-repaired) type's deterministic guidance,
# prunes topical related tags no longer justified, and applies review-tag changes ONLY when justified by
# the repaired type. Every managed block + identity + source id/sha/path/timestamps + document_type +
# source/type tag stay untouched. Fail-safe + idempotent, same as the repair planner.

# Review-tag changes are gated on the repaired document_type so ``--add-review``/``--drop-review`` can
# never become a broad, untyped mutation path when the script is reused (amendment 1).
_REVIEW_ADD_JUSTIFIED: dict[str, frozenset[str]] = {
    "specification_template": frozenset({"review/project-context"}),
}
_REVIEW_DROP_JUSTIFIED: dict[str, frozenset[str]] = {
    "specification_template": frozenset({"review/metadata-only"}),
}
_RELATED_PREFIX = "related/"


def _has_graph_links(card_text: str) -> bool:
    return ng.REL_BLOCK_BEGIN in card_text


def _related_tag_grounded(slug: str, document_type: str, card_text: str) -> bool:
    """Deterministic grounding for one ``related/*`` tag from the card's own facts (never body-derived)."""
    if slug == "project":
        return any(_frontmatter_value(card_text, k) for k in
                   ("project_number", "project_key", "canonical_project_key", "procore_project_id"))
    fam = ng._RELATED_TAG_CONTENT.get(slug)
    if fam is not None:  # topical: grounded iff the repaired type's content family matches
        return ng._DOCTYPE_CONTENT.get(document_type) == fam
    return True  # company/person/email/attachment: not disprovable from the card → never prune


def prune_ungrounded_related_tags(card_text: str, document_type: str) -> tuple[str, list[str]]:
    """Drop topical ``related/*`` tags no longer justified by the repaired type.

    No-op (returns the input unchanged) when a ``gc-graph-links`` block is present: those related tags
    are justified by real relationship links and must not be pruned in this pass (amendment 2).
    """
    if _has_graph_links(card_text):
        return card_text, []
    ok, tags, _f, _l = ng.parse_frontmatter_tags(card_text)
    if not ok:
        return card_text, []
    ungrounded = [t for t in tags if t.startswith(_RELATED_PREFIX)
                  and not _related_tag_grounded(t.split("/", 1)[1], document_type, card_text)]
    if not ungrounded:
        return card_text, []
    txt, _r = ng.remove_frontmatter_tags(card_text, ungrounded)
    return (txt, ungrounded) if txt is not None else (card_text, [])


def _justified_review_changes(document_type: str, add: tuple[str, ...],
                              remove: tuple[str, ...]) -> tuple[list[str], list[str], list[str]]:
    """Filter requested review-tag add/drop to the subset justified by the repaired type (amendment 1)."""
    add_j = _REVIEW_ADD_JUSTIFIED.get(document_type, frozenset())
    drop_j = _REVIEW_DROP_JUSTIFIED.get(document_type, frozenset())
    add_ok = [t for t in add if t in add_j]
    drop_ok = [t for t in remove if t in drop_j]
    skipped = [t for t in add if t not in add_j] + [t for t in remove if t not in drop_j]
    return add_ok, drop_ok, skipped


def adjust_review_tags(card_text: str, add_tags: list[str],
                       remove_tags: list[str]) -> tuple[str, list[str], list[str]]:
    """Remove then add review tags (already type-filtered). Idempotent; preserves everything else."""
    txt, added, removed = card_text, [], []
    if remove_tags:
        _ok, existing, _f, _l = ng.parse_frontmatter_tags(txt)
        present = [t for t in remove_tags if t in existing]
        if present:
            nxt, _r = ng.remove_frontmatter_tags(txt, present)
            if nxt is not None:
                txt, removed = nxt, present
    if add_tags:
        _ok, existing, _f, _l = ng.parse_frontmatter_tags(txt)
        to_add = [t for t in add_tags if t not in existing]
        if to_add:
            nxt, _r = ng.apply_tags(txt, to_add)
            if nxt is not None:
                txt, added = nxt, to_add
    return txt, added, removed


@dataclass(frozen=True)
class CardPolishPlan:
    action: str  # "polish" | "noop" | "skip"
    document_type: str
    skip_reason: str | None
    followup_changed: bool
    related_pruned: tuple[str, ...]
    review_added: tuple[str, ...]
    review_removed: tuple[str, ...]
    review_skipped: tuple[str, ...]
    new_text: str | None


def plan_card_polish(card_text: str, detail: dict, *, add_review: tuple[str, ...] = (),
                     remove_review: tuple[str, ...] = ()) -> CardPolishPlan:
    """Plan the post-repair polish for one card (Follow-Up + stale related/review tags only)."""
    document_type = str(_frontmatter_value(card_text, "document_type") or "").strip()
    guidance = _pm_guidance(document_type)

    # 1. Regenerate Follow-Up from the (already-repaired) type's deterministic guidance.
    txt, reason = replace_section_body(
        card_text, "## Follow-Up", [f"- [ ] {f}" for f in guidance["followup"]])
    if txt is None:
        return CardPolishPlan("skip", document_type, f"Follow-Up:{reason}", False, (), (), (), (), None)
    followup_changed = txt != card_text

    # 2. Prune topical related tags no longer justified (skipped entirely when graph links exist).
    txt, pruned = prune_ungrounded_related_tags(txt, document_type)

    # 3. Apply only the review-tag changes justified by the repaired type.
    add_ok, drop_ok, review_skipped = _justified_review_changes(
        document_type, tuple(add_review), tuple(remove_review))
    txt, added, removed = adjust_review_tags(txt, add_ok, drop_ok)

    if txt == card_text:
        return CardPolishPlan("noop", document_type, None, False, (), (), (),
                              tuple(review_skipped), None)
    return CardPolishPlan("polish", document_type, None, followup_changed, tuple(pruned),
                          tuple(added), tuple(removed), tuple(review_skipped), txt)
