"""Local note-graph: deterministic candidate retrieval + qwen2.5:14b vetting + reciprocal link/tag writers.

Phase 10C. The local model is ADVISORY ONLY: it vets candidate relationships built deterministically
from existing index/card metadata and may pick from fixed enums; it never writes files, invents tags/
titles, or creates notes. All writes are performed by the deterministic helpers here (managed
relationship blocks + controlled frontmatter tags), confined to managed regions. No source-file read,
no scan, no queue/DB/runtime mutation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --- Enums --------------------------------------------------------------------------------------
RELATIONSHIP_TYPES = frozenset({
    "same_project", "same_company", "same_person", "same_decision", "same_meeting", "same_schedule",
    "same_cost_topic", "same_contract_topic", "same_rfi_or_submittal_topic",
    "same_drawing_or_scope_area", "same_reference_family", "supersedes_or_revises",
    "supports_or_explains", "potential_duplicate", "weak_context_only", "reject",
})
# Types we will actually write reciprocal links for.
_NON_APPLY = frozenset({"reject", "weak_context_only", "potential_duplicate"})
APPLY_TYPES = RELATIONSHIP_TYPES - _NON_APPLY

# --- Controlled tag taxonomy --------------------------------------------------------------------
CONTENT_TYPE_TAGS = frozenset(
    f"source/type/{t}" for t in
    ("drawing", "schedule", "submittal", "rfi", "meeting", "cost", "contract", "scope-of-work",
     "reference", "template-form", "spreadsheet", "correspondence", "unknown"))
DISPOSITION_TAGS = frozenset(
    f"source/disposition/{t}" for t in ("auto-card-high", "metadata-only", "needs-review", "reference"))
RELATED_TAGS = frozenset(
    f"related/{t}" for t in
    ("project", "company", "person", "schedule", "cost", "contract", "scope", "meeting", "rfi",
     "submittal", "drawing", "reference"))
REVIEW_TAGS = frozenset(
    f"review/{t}" for t in ("needs-human-check", "weak-relationship", "qwen-vetted", "metadata-only"))
APPROVED_QWEN_TAGS = RELATED_TAGS | REVIEW_TAGS  # the only tags Qwen may pick

_DOCTYPE_CONTENT = {
    "architectural_drawing": "drawing", "structural_drawing": "drawing", "mep_drawing": "drawing",
    "civil_drawing": "drawing", "drawing": "drawing", "schedule": "schedule", "submittal": "submittal",
    "rfi": "rfi", "meeting_minutes": "meeting", "cost_report": "cost", "project_controls": "cost",
    "cost_document": "cost", "pay_application": "cost", "change_order": "cost",
    "potential_change_order": "cost", "contract": "contract", "subcontract": "contract",
    "purchase_order": "contract", "scope_of_work": "scope-of-work", "bid_package": "scope-of-work",
    "reference_document": "reference", "template_form": "template-form", "spreadsheet": "spreadsheet",
    "communications_matrix": "spreadsheet", "coordination_matrix": "spreadsheet",
    "staffing_report": "spreadsheet", "general_pdf": "correspondence",
    "general_document": "correspondence",
}
_DISP_TAG = {"auto_card_high": "auto-card-high", "metadata_only": "metadata-only"}
_REL_TAG = {
    "same_project": "project", "same_company": "company", "same_person": "person",
    "same_schedule": "schedule", "same_cost_topic": "cost", "same_contract_topic": "contract",
    "same_rfi_or_submittal_topic": "rfi", "same_drawing_or_scope_area": "drawing",
    "same_meeting": "meeting", "same_reference_family": "reference",
}
_STRICTER_TYPES = frozenset({"template_form", "reference_document", "metadata_only",
                             "spreadsheet", "communications_matrix", "coordination_matrix"})

LOCAL_MODEL = "qwen2.5:14b"
REL_BLOCK_BEGIN = "<!-- hb-related-notes:start -->"
REL_BLOCK_END = "<!-- hb-related-notes:end -->"
_RELATED_SECTIONS = ("## Related Project", "## Related People / Companies", "## Related Decisions",
                     "## Related Meetings")
_SECTION_FOR_REL = {
    "same_project": "## Related Project", "same_company": "## Related People / Companies",
    "same_person": "## Related People / Companies", "same_meeting": "## Related Meetings",
    "same_decision": "## Related Decisions",
}
_GENERIC_TOKENS = frozenset({
    "the", "and", "for", "of", "a", "report", "log", "form", "template", "cover", "sheet", "notes",
    "project", "final", "draft", "copy", "rev", "new", "old", "list", "matrix", "general",
})
_CONF_THRESHOLD_DEFAULT = 0.80
_REASON_MAX = 200


# --- Note facts ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class NoteFact:
    note_id: str
    note_rel: str
    basename: str
    display: str
    project: str | None
    vendor: str | None
    document_type: str
    document_number: str | None
    doc_date: str | None
    disposition: str | None
    review_needed: bool
    title_tokens: frozenset[str]
    existing_tags: tuple[str, ...]
    summary_text: str
    # Canonical Procore identity parsed from the card's hb-project-identity block (Phase 10D).
    canonical_project_key: str | None = None
    procore_project_id: str | None = None


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _display_name(basename: str) -> str:
    return re.sub(r"__[A-Za-z0-9_-]{8,}$", "", basename).strip() or basename


def _title_tokens(name: str) -> frozenset[str]:
    toks = re.split(r"[^A-Za-z0-9]+", _display_name(name).lower())
    return frozenset(t for t in toks if len(t) >= 4 and t not in _GENERIC_TOKENS and not t.isdigit())


def _frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[:end] if end != -1 else text
    m = re.search(rf"(?m)^{re.escape(key)}:\s*(.*?)\s*$", block)
    return (m.group(1).strip().strip('"') or None) if m else None


def parse_frontmatter_tags(text: str) -> tuple[bool, list[str], int, int]:
    """Return (ok, tags, first_tag_line_idx, last_tag_line_idx) for a BLOCK-style ``tags:`` list.

    ok=False when there is no frontmatter, no block-style tags list, or the list is inline/scalar/
    malformed (caller then skips the note unless normalization is explicitly allowed).
    """
    lines = text.splitlines()
    if not text.startswith("---"):
        return False, [], -1, -1
    # locate frontmatter bounds
    fm_end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
    if fm_end == -1:
        return False, [], -1, -1
    tag_hdr = next((i for i in range(1, fm_end) if re.match(r"^tags:\s*$", lines[i])), -1)
    if tag_hdr == -1:
        return False, [], -1, -1  # inline `tags: [..]`/scalar/absent → not block-style
    tags, first, last = [], -1, -1
    for i in range(tag_hdr + 1, fm_end):
        m = re.match(r"^(\s*)-\s+(.+?)\s*$", lines[i])
        if not m:
            break
        tags.append(m.group(2).strip())
        first = i if first == -1 else first
        last = i
    if first == -1:
        return False, [], -1, -1
    return True, tags, first, last


def sanitize_tag(tag: str) -> str | None:
    """Lowercase, `/`-namespaced, slug-safe; must be in an approved set. Else None."""
    t = str(tag or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:/[a-z0-9][a-z0-9-]*)+", t):
        return None
    if t in CONTENT_TYPE_TAGS or t in DISPOSITION_TAGS or t in RELATED_TAGS or t in REVIEW_TAGS:
        return t
    return None


def content_tags_for(fact: NoteFact) -> list[str]:
    """Deterministic content-type + disposition tags for a note (never model-chosen)."""
    out = [f"source/type/{_DOCTYPE_CONTENT.get(fact.document_type, 'unknown')}"]
    if fact.document_type == "reference_document":
        out.append("source/disposition/reference")
    elif fact.disposition in _DISP_TAG:
        out.append(f"source/disposition/{_DISP_TAG[fact.disposition]}")
    if fact.review_needed:
        out.append("source/disposition/needs-review")
    return [t for t in out if t in CONTENT_TYPE_TAGS or t in DISPOSITION_TAGS]


def relationship_tags_for(rel_type: str) -> list[str]:
    """Deterministic related/* + review/qwen-vetted tags implied by an approved relationship type."""
    out = ["review/qwen-vetted"]
    slug = _REL_TAG.get(rel_type)
    if slug:
        out.append(f"related/{slug}")
    return out


def note_fact_from(repo: Any, row: dict[str, Any], card_text: str) -> NoteFact:
    """Build a NoteFact from a generated-note row + DB detail + analyzer + the card markdown."""
    from . import source_analyzers
    source_id = str(row["source_id"])
    note_rel = str(row["note_rel_path"])
    detail = repo.get_source_detail(source_id) or {}
    a = source_analyzers.from_detail(detail)
    basename = Path(note_rel).stem
    ok, tags, _f, _l = parse_frontmatter_tags(card_text)
    disp = _frontmatter_value(card_text, "source_disposition")
    review = _frontmatter_value(card_text, "review_status") == "needs_review"
    summary = "\n".join(_section_body(card_text, "## Source Summary")
                        + _section_body(card_text, "## Key Facts"))[:1500]
    # Canonical Procore identity from the managed hb-project-identity block, if present.
    from .source_project_identity import parse_identity_marker
    ident = parse_identity_marker(card_text) or {}
    return NoteFact(
        note_id=source_id, note_rel=note_rel, basename=basename, display=_display_name(basename),
        project=_norm(detail.get("project_number") or detail.get("project_key")) or None,
        vendor=_norm(a.vendor) or None, document_type=a.document_type,
        document_number=_norm(a.document_number) or None, doc_date=_norm(a.doc_date) or None,
        disposition=disp, review_needed=review, title_tokens=_title_tokens(basename),
        existing_tags=tuple(tags if ok else []), summary_text=summary,
        canonical_project_key=_norm(ident.get("project_key")) or None,
        procore_project_id=_norm(ident.get("procore_project_id")) or None)


def _section_body(text: str, heading: str) -> list[str]:
    out, cap = [], False
    for ln in text.splitlines():
        if ln == heading:
            cap = True
            continue
        if cap and ln.startswith("## "):
            break
        if cap and ln.strip():
            out.append(ln)
    return out


# --- Deterministic candidate retrieval ----------------------------------------------------------
@dataclass(frozen=True)
class Candidate:
    a: NoteFact
    b: NoteFact
    strong: int
    signals: tuple[str, ...]


# Signals that are informative for reporting but NOT strong enough alone to make a candidate.
_WEAK_SIGNALS = frozenset({"shared_title_phrase", "same_document_type"})


def _pair_signals(a: NoteFact, b: NoteFact) -> list[str]:
    """Deterministic commonality signals (content-based, never path/folder). Distinct project bases."""
    s = []
    if a.project and b.project and a.project == b.project:
        s.append("same_project_number")  # folder-derived NN-NNN-NN on the DB source row
    if a.canonical_project_key and b.canonical_project_key and \
            a.canonical_project_key == b.canonical_project_key:
        s.append("same_project_key")  # canonical Procore key from the identity block
    if a.procore_project_id and b.procore_project_id and a.procore_project_id == b.procore_project_id:
        s.append("same_procore_id")
    if a.vendor and b.vendor and a.vendor == b.vendor:
        s.append("same_vendor")
    if (a.document_number and b.document_number and a.document_number == b.document_number
            and a.document_type == b.document_type):
        s.append("same_document_number")
    if a.document_type == b.document_type and a.document_type not in (
            "general_pdf", "general_document"):
        s.append("same_document_type")  # weak / reporting only
    shared = a.title_tokens & b.title_tokens
    if len(shared) >= 2:
        s.append("shared_title_phrase")
    if (a.doc_date and b.doc_date and a.doc_date == b.doc_date
            and a.project and a.project == b.project):
        s.append("same_date_same_project")
    return s


def is_candidate(a: NoteFact, b: NoteFact) -> tuple[bool, list[str]]:
    """Eligible for vetting iff enough STRONG signals (stricter for generic/template/reference)."""
    if a.note_id == b.note_id:
        return False, []
    signals = _pair_signals(a, b)
    strong = [x for x in signals if x not in _WEAK_SIGNALS]
    need = 2 if (a.document_type in _STRICTER_TYPES or b.document_type in _STRICTER_TYPES) else 1
    return (len(strong) >= need, signals)


def candidate_basis_counts(candidates: list["Candidate"]) -> dict[str, int]:
    """Count how many candidate pairs carry each deterministic signal (basis)."""
    from collections import Counter
    counts: Counter[str] = Counter()
    for c in candidates:
        for sig in c.signals:
            counts[sig] += 1
    return dict(sorted(counts.items()))


def build_candidates(facts: list[NoteFact], *, max_per_note: int = 10,
                     max_relationships: int = 50) -> list[Candidate]:
    """All eligible unordered pairs, stable-sorted by strength then note ids; bounded."""
    cands: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    ordered = sorted(facts, key=lambda f: f.note_rel)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            key = tuple(sorted((a.note_id, b.note_id)))
            if key in seen:
                continue
            ok, signals = is_candidate(a, b)
            if not ok:
                continue
            seen.add(key)
            strong = len([x for x in signals if x != "shared_title_phrase"])
            cands.append(Candidate(a=a, b=b, strong=strong, signals=tuple(signals)))
    cands.sort(key=lambda c: (-c.strong, c.a.note_rel, c.b.note_rel))
    # per-note cap
    per: dict[str, int] = {}
    capped: list[Candidate] = []
    for c in cands:
        if per.get(c.a.note_id, 0) >= max_per_note or per.get(c.b.note_id, 0) >= max_per_note:
            continue
        capped.append(c)
        per[c.a.note_id] = per.get(c.a.note_id, 0) + 1
        per[c.b.note_id] = per.get(c.b.note_id, 0) + 1
        if len(capped) >= max_relationships:
            break
    return capped


# --- Qwen vetting (advisory; JSON, schema-bound) ------------------------------------------------
VETTING_SYSTEM_PROMPT = (
    "You are vetting whether two existing Obsidian notes should be linked.\n"
    "Use ONLY the provided note summaries and deterministic commonality evidence.\n"
    "Do not invent facts, dates, companies, projects, statuses, or costs.\n"
    "If the relationship is weak, generic, path-only, or uncertain, reject it.\n"
    "Choose only from the allowed relationship_type enum. Choose only from allowed_tags.\n"
    "Return VALID JSON only with keys: approved (bool), relationship_type (enum), confidence (0..1),\n"
    "reason (<=200 chars), tags_for_source (list), tags_for_target (list).\n"
)


def build_vetting_prompt(a: NoteFact, b: NoteFact, signals: list[str]) -> str:
    parts = [
        "NOTE A SUMMARY:", a.summary_text or "(none)", "",
        "NOTE B SUMMARY:", b.summary_text or "(none)", "",
        "DETERMINISTIC COMMONALITY EVIDENCE: " + (", ".join(signals) or "none"),
        f"A document_type={a.document_type}; B document_type={b.document_type}",
        "allowed relationship_type: " + ", ".join(sorted(RELATIONSHIP_TYPES)),
        "allowed_tags: " + ", ".join(sorted(APPROVED_QWEN_TAGS)),
        "Reject if the evidence is weak or you are uncertain. Return JSON only.",
    ]
    return "\n".join(parts)


def validate_vet(obj: Any, *, threshold: float = _CONF_THRESHOLD_DEFAULT) -> dict[str, Any] | None:
    """Schema-validate the model's JSON. Return an approved dict or None (reject / no write)."""
    if not isinstance(obj, dict):
        return None
    if obj.get("approved") is not True:
        return None
    rtype = obj.get("relationship_type")
    if rtype not in APPLY_TYPES:  # rejects reject/weak/duplicate and anything off-enum
        return None
    try:
        conf = float(obj.get("confidence"))
    except (TypeError, ValueError):
        return None
    if not (0.0 <= conf <= 1.0) or conf < threshold:
        return None
    reason = str(obj.get("reason") or "").strip()
    if not reason or len(reason) > _REASON_MAX:
        return None
    tfs = [sanitize_tag(t) for t in (obj.get("tags_for_source") or [])]
    tft = [sanitize_tag(t) for t in (obj.get("tags_for_target") or [])]
    if any(t is None for t in tfs) or any(t is None for t in tft):
        return None  # any unknown/invented tag → reject the whole vet
    return {"relationship_type": rtype, "confidence": round(conf, 2), "reason": reason,
            "tags_for_source": [t for t in tfs if t], "tags_for_target": [t for t in tft if t]}


def vet_candidate(client: Any, cand: Candidate, *, threshold: float = _CONF_THRESHOLD_DEFAULT,
                  ) -> tuple[dict[str, Any] | None, str]:
    """Call local Ollama JSON vetting; return (approved_dict | None, reason). Never raises."""
    import json

    from hb_assistant.construction.classification.client import OllamaUnavailable
    prompt = build_vetting_prompt(cand.a, cand.b, list(cand.signals))
    try:
        raw = client.generate_json(system=VETTING_SYSTEM_PROMPT, prompt=prompt)
    except OllamaUnavailable as exc:
        return None, f"ollama:{exc}"
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return None, "invalid_json"
    approved = validate_vet(obj, threshold=threshold)
    return (approved, "ok") if approved else (None, "rejected")


# --- Deterministic writers (managed regions only) -----------------------------------------------
def build_wiki_link(target: NoteFact) -> str:
    """Vault-relative, disambiguated wiki link; never an absolute path."""
    return f"[[{target.note_rel[:-3] if target.note_rel.endswith('.md') else target.note_rel}|{target.display}]]"


def choose_section(rel_types: set[str]) -> str:
    for rel in ("same_project", "same_company", "same_person", "same_meeting", "same_decision"):
        if rel in rel_types and _SECTION_FOR_REL.get(rel) in _RELATED_SECTIONS:
            return _SECTION_FOR_REL[rel]
    return "## Related Project"


def apply_tags(text: str, new_tags: list[str], *, allow_normalize: bool = False) -> tuple[str | None, str]:
    """Append controlled tags into the existing block-style frontmatter tags list (preserve all else).

    Returns (new_text | None, reason). Skips (None) when frontmatter tags are not block-style unless
    allow_normalize. Never removes/dedups existing tags; caps NEW tags at 8.
    """
    clean = []
    for t in new_tags:
        st = sanitize_tag(t)
        if st and st not in clean:
            clean.append(st)
    ok, existing, _first, last = parse_frontmatter_tags(text)
    if not ok:
        return (None, "frontmatter_not_block_style") if not allow_normalize else (None, "normalize_unsupported")
    to_add = [t for t in clean if t not in existing][:8]
    if not to_add:
        return text, "no_new_tags"
    lines = text.splitlines(keepends=True)
    indent = re.match(r"^(\s*)-", lines[last]).group(1)
    insert = "".join(f"{indent}- {t}\n" for t in to_add)
    # insert right after the last existing tag line, preserving everything else byte-for-byte
    newline = "" if lines[last].endswith("\n") else "\n"
    lines[last] = lines[last] + newline + insert.rstrip("\n") + ("\n" if lines[last].endswith("\n") else "")
    return "".join(lines), "ok"


def upsert_related_block(text: str, link_lines: list[str], *, section: str) -> tuple[str | None, str]:
    """Insert/replace the single managed hb-related-notes block under ``section``.

    Preserves everything outside the block; stable-sorted unique links. Returns (new_text|None, reason).
    """
    uniq = sorted({ln for ln in link_lines if ln.strip()})
    block = [REL_BLOCK_BEGIN, *uniq, REL_BLOCK_END]
    lines = text.splitlines()
    bs = [i for i, ln in enumerate(lines) if ln.strip() == REL_BLOCK_BEGIN]
    be = [i for i, ln in enumerate(lines) if ln.strip() == REL_BLOCK_END]
    trailing = "\n" if text.endswith("\n") else ""
    if len(bs) == 1 and len(be) == 1 and be[0] > bs[0]:
        new = lines[:bs[0]] + block + lines[be[0] + 1:]
        return "\n".join(new) + trailing, "updated"
    if bs or be:
        return None, "ambiguous_existing_block"
    # insert at end of the chosen section (before the next "## " heading), else append section.
    sec = next((i for i, ln in enumerate(lines) if ln == section), -1)
    if sec == -1:
        new = lines + ["", section, "", *block]
        return "\n".join(new) + trailing, "section_appended"
    end = next((i for i in range(sec + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    insert_at = end
    while insert_at > sec + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new = lines[:insert_at] + ["", *block] + lines[insert_at:]
    return "\n".join(new) + trailing, "inserted"

