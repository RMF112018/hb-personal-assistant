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
    "supports_or_explains", "potential_duplicate", "same_source_duplicate", "same_email_duplicate",
    "weak_context_only", "reject",
})
# Review-only relationship types: recognized for reporting/vetting but NEVER written as durable
# reciprocal links in Phase 10G. `same_project` is context/secondary evidence only (a project link is
# not a durable relationship — Phase 10G amendment). The duplicate types describe same-source /
# same-email pairs surfaced for human review, never durably linked by default.
REVIEW_ONLY_TYPES = frozenset({"potential_duplicate", "same_source_duplicate", "same_email_duplicate",
                               "same_project"})
# Types we will actually write reciprocal links for. same_project + duplicate types are excluded, so
# validate_vet rejects them for durable apply (no link, and same_project gets no tag either).
_NON_APPLY = frozenset({"reject", "weak_context_only"}) | REVIEW_ONLY_TYPES
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
     "submittal", "drawing", "reference", "email", "attachment"))
REVIEW_TAGS = frozenset(
    f"review/{t}" for t in ("needs-human-check", "weak-relationship", "qwen-vetted", "metadata-only",
                            "project-context"))
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
    "general_document": "correspondence", "email": "correspondence",
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
REL_BLOCK_BEGIN = "<!-- gc-graph-links:start -->"
REL_BLOCK_END = "<!-- gc-graph-links:end -->"
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
    # Graph-safe email facts parsed from the card's hb-email block (Phase 10E). All deterministic
    # metadata — never body text. Participant/attachment refs are hashes, domains are plain.
    thread_topic: str | None = None
    subject_norm: str | None = None
    from_domain: str | None = None
    email_domains: frozenset[str] = frozenset()
    participant_hashes: frozenset[str] = frozenset()
    attachment_hashes: frozenset[str] = frozenset()
    project_alias: str | None = None
    # Graph-safe attachment facts parsed from the card's hb-email-attachment block (Phase 10F).
    parent_email_hash: str | None = None
    attachment_sha256s: frozenset[str] = frozenset()
    attachment_extension: str | None = None
    # Duplicate-detection facts (Phase 10G correction): per-source content hash (from DB detail) and
    # the email message-id hash (from the hb-email block). Equal values => same-source / same-email
    # duplicates, which are review-only and veto durable candidate eligibility.
    source_sha256: str | None = None
    message_id_hash: str | None = None


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
    # Graph-safe email facts from the managed hb-email block (Phase 10E), if present.
    from .source_email_archive import parse_email_marker

    def _split(val: str | None) -> frozenset[str]:
        return frozenset(x for x in (val or "").split(",") if x)
    em = parse_email_marker(card_text) or {}
    email_domains = _split(em.get("recipient_domains"))
    if em.get("from_domain"):
        email_domains = email_domains | {str(em["from_domain"]).lower()}
    # Graph-safe attachment facts from the managed hb-email-attachment block (Phase 10F), if present.
    from .source_email_attachments import parse_email_attachment_marker
    ea = parse_email_attachment_marker(card_text) or {}
    return NoteFact(
        note_id=source_id, note_rel=note_rel, basename=basename, display=_display_name(basename),
        project=_norm(detail.get("project_number") or detail.get("project_key")) or None,
        vendor=_norm(a.vendor) or None, document_type=a.document_type,
        document_number=_norm(a.document_number) or None, doc_date=_norm(a.doc_date) or None,
        disposition=disp, review_needed=review, title_tokens=_title_tokens(basename),
        existing_tags=tuple(tags if ok else []), summary_text=summary,
        canonical_project_key=_norm(ident.get("project_key")) or None,
        procore_project_id=_norm(ident.get("procore_project_id")) or None,
        thread_topic=_norm(em.get("thread_topic")) or None,
        subject_norm=_norm(em.get("subject_norm")) or None,
        from_domain=(str(em.get("from_domain")).lower() or None) if em.get("from_domain") else None,
        email_domains=email_domains,
        participant_hashes=_split(em.get("participant_hashes")),
        attachment_hashes=_split(em.get("attachment_hashes")),
        project_alias=_norm(em.get("project_alias")) or None,
        parent_email_hash=_norm(ea.get("parent_email_hash")) or None,
        attachment_sha256s=_split(ea.get("attachment_sha256")),
        attachment_extension=_norm(ea.get("attachment_extension")) or None,
        source_sha256=_norm(detail.get("content_sha256")) or None,
        message_id_hash=_norm(em.get("message_id_hash")) or None)


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
# same_email_domain is weak: a shared big-GC/owner domain must not link two unrelated emails.
_WEAK_SIGNALS = frozenset({"shared_title_phrase", "same_document_type", "same_email_domain",
                           "same_attachment_extension"})

# Phase 10G bounded eligibility (mode="primary_secondary"): a durable link requires ONE strong PRIMARY
# signal (real relationship evidence) AND at least one further strong signal (PRIMARY or SECONDARY).
# Project signals are SECONDARY/context only — never sufficient alone (a single-project bounded set makes
# "same project" universal and uninformative). same_attachment_sha256 is neither: it is DUPLICATE
# evidence (same file), routed to review-only, never a durable-link basis on its own (Phase 10G amendment).
PRIMARY_STRONG = frozenset({"same_parent_email", "same_document_number", "same_thread_topic",
                            "same_subject_normalized"})
SECONDARY_STRONG = frozenset({"same_participant", "same_vendor", "same_project_alias",
                              "same_date_same_project", "same_procore_id", "same_project_key",
                              "same_project_number", "same_attachment_ref"})
DUPLICATE_SIGNALS = frozenset({"same_attachment_sha256", "same_source_sha256",
                               "same_message_id_hash"})


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
    # Email metadata signals (Phase 10E) — deterministic, never body-derived. Strong: thread topic,
    # normalized subject, a shared participant, a shared attachment, a subject-detected project alias.
    if a.thread_topic and b.thread_topic and a.thread_topic == b.thread_topic:
        s.append("same_thread_topic")
    if a.subject_norm and b.subject_norm and a.subject_norm == b.subject_norm:
        s.append("same_subject_normalized")
    if a.participant_hashes & b.participant_hashes:
        s.append("same_participant")
    if a.attachment_hashes & b.attachment_hashes:
        s.append("same_attachment_ref")
    if a.project_alias and b.project_alias and a.project_alias == b.project_alias:
        s.append("same_project_alias")
    if a.email_domains & b.email_domains:
        s.append("same_email_domain")  # weak / reporting only
    # Attachment signals (Phase 10F) — deterministic. Strong: same parent email, same attachment content
    # sha256. Weak: same file extension only (a shared ".pdf" must not link unrelated attachments).
    if a.parent_email_hash and b.parent_email_hash and a.parent_email_hash == b.parent_email_hash:
        s.append("same_parent_email")
    if a.attachment_sha256s & b.attachment_sha256s:
        s.append("same_attachment_sha256")
    if a.attachment_extension and b.attachment_extension and \
            a.attachment_extension == b.attachment_extension:
        s.append("same_attachment_extension")  # weak / reporting only
    # Duplicate / same-source evidence (Phase 10G correction) — DUPLICATE signals: equal source content
    # hash (same file bytes) or equal email message-id hash (same email). Review-only; these VETO
    # durable candidate eligibility even when the pair also shares thread/subject/participant/project.
    if a.source_sha256 and b.source_sha256 and a.source_sha256 == b.source_sha256:
        s.append("same_source_sha256")
    if a.message_id_hash and b.message_id_hash and a.message_id_hash == b.message_id_hash:
        s.append("same_message_id_hash")
    return s


def is_candidate(a: NoteFact, b: NoteFact, *, mode: str = "default") -> tuple[bool, list[str]]:
    """Eligible for vetting.

    mode="default" (Phase 10C): enough STRONG signals (stricter for generic/template/reference).
    mode="primary_secondary" (Phase 10G bounded apply): require ONE strong PRIMARY signal AND at least
    one further strong signal (PRIMARY or SECONDARY). Weak and DUPLICATE (same-sha) signals never count,
    so project-only / duplicate-only / weak-only pairs are excluded from durable candidates.
    """
    if a.note_id == b.note_id:
        return False, []
    signals = _pair_signals(a, b)
    if mode == "primary_secondary":
        # Duplicate / same-source evidence VETOES durable eligibility — a same-file or same-email pair
        # is review-only even when it also shares thread/subject/participant/project primaries (this is
        # exactly the hole that durably linked two duplicate email cards in the first 10G apply).
        if is_duplicate_pair(signals):
            return False, signals
        primary = [x for x in signals if x in PRIMARY_STRONG]
        strong = [x for x in signals if x in PRIMARY_STRONG or x in SECONDARY_STRONG]
        return (len(primary) >= 1 and len(strong) >= 2, signals)
    strong = [x for x in signals if x not in _WEAK_SIGNALS]
    need = 2 if (a.document_type in _STRICTER_TYPES or b.document_type in _STRICTER_TYPES) else 1
    return (len(strong) >= need, signals)


def is_duplicate_pair(signals: list[str] | tuple[str, ...]) -> bool:
    """True when the pair shares attachment content sha256 — same-file/duplicate evidence (review-only)."""
    return any(s in DUPLICATE_SIGNALS for s in signals)


def candidate_basis_counts(candidates: list["Candidate"]) -> dict[str, int]:
    """Count how many candidate pairs carry each deterministic signal (basis)."""
    from collections import Counter
    counts: Counter[str] = Counter()
    for c in candidates:
        for sig in c.signals:
            counts[sig] += 1
    return dict(sorted(counts.items()))


def build_candidates(facts: list[NoteFact], *, max_per_note: int = 10,
                     max_relationships: int = 50, mode: str = "default") -> list[Candidate]:
    """All eligible unordered pairs, stable-sorted by strength then note ids; bounded.

    ``mode`` is passed to ``is_candidate`` (Phase 10G uses "primary_secondary").
    """
    cands: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    ordered = sorted(facts, key=lambda f: f.note_rel)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            key = tuple(sorted((a.note_id, b.note_id)))
            if key in seen:
                continue
            ok, signals = is_candidate(a, b, mode=mode)
            if not ok:
                continue
            seen.add(key)
            strong = len([x for x in signals if x not in _WEAK_SIGNALS])
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
    "Use ONLY the provided structured facts and deterministic commonality evidence. No note bodies,\n"
    "summaries, titles, paths, addresses, message ids, or file names are provided — do not ask for them.\n"
    "Do not invent facts, dates, companies, projects, statuses, or costs.\n"
    "If the relationship is weak, generic, project-only, duplicate-only, or uncertain, reject it.\n"
    "For same-file / same-content (duplicate) evidence choose potential_duplicate.\n"
    "Choose only from the allowed relationship_type enum. Choose only from allowed_tags.\n"
    "Return VALID JSON only with keys: approved (bool), relationship_type (enum), confidence (0..1),\n"
    "reason (<=200 chars), tags_for_source (list), tags_for_target (list).\n"
)


def _vetting_fact_line(f: NoteFact) -> str:
    """Bounded, fact-only descriptor for the vetting prompt — never bodies/titles/paths/names."""
    kind = ("attachment" if f.attachment_extension
            else "email" if (f.thread_topic or f.subject_norm) else "document")
    return "; ".join([
        f"kind={kind}",
        f"document_type={f.document_type}",
        f"document_number={f.document_number or 'none'}",
        f"vendor={f.vendor or 'none'}",
        f"has_project_identity={'yes' if f.procore_project_id else 'no'}",
    ])


def build_vetting_prompt(a: NoteFact, b: NoteFact, signals: list[str]) -> str:
    parts = [
        "Decide only from the structured facts + deterministic evidence below. No note bodies are provided.",
        "NOTE A FACTS: " + _vetting_fact_line(a),
        "NOTE B FACTS: " + _vetting_fact_line(b),
        "DETERMINISTIC COMMONALITY EVIDENCE: " + (", ".join(signals) or "none"),
        "allowed relationship_type: " + ", ".join(sorted(RELATIONSHIP_TYPES)),
        "allowed_tags: " + ", ".join(sorted(APPROVED_QWEN_TAGS)),
        "Reject if the evidence is weak, project-only, duplicate-only, or you are uncertain. "
        "For same-file/duplicate evidence choose potential_duplicate. Return JSON only.",
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
    """Insert/replace the single managed gc-graph-links block under ``section``.

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


def _related_block_bounds(lines: list[str]) -> tuple[int, int] | None | str:
    """Return (begin_idx, end_idx) for the single managed block, None if absent, "ambiguous" if not
    exactly one well-formed pair."""
    bs = [i for i, ln in enumerate(lines) if ln.strip() == REL_BLOCK_BEGIN]
    be = [i for i, ln in enumerate(lines) if ln.strip() == REL_BLOCK_END]
    if not bs and not be:
        return None
    if len(bs) != 1 or len(be) != 1 or be[0] <= bs[0]:
        return "ambiguous"
    return bs[0], be[0]


def related_block_entries(text: str) -> list[str] | None:
    """Non-empty link lines inside the managed gc-graph-links block ([] if block empty, None if absent
    or ambiguous)."""
    lines = text.splitlines()
    bounds = _related_block_bounds(lines)
    if not isinstance(bounds, tuple):
        return None
    bs, be = bounds
    return [ln for ln in lines[bs + 1:be] if ln.strip()]


def remove_related_block(text: str) -> tuple[str | None, str]:
    """Delete the single managed gc-graph-links block plus one adjacent blank line above it.

    Returns (new_text|None, reason): 'removed' | 'absent' | 'ambiguous_existing_block'.
    """
    lines = text.splitlines()
    bounds = _related_block_bounds(lines)
    if bounds is None:
        return text, "absent"
    if bounds == "ambiguous":
        return None, "ambiguous_existing_block"
    bs, be = bounds
    trailing = "\n" if text.endswith("\n") else ""
    start = bs - 1 if (bs > 0 and not lines[bs - 1].strip()) else bs
    new = lines[:start] + lines[be + 1:]
    return ("\n".join(new) + trailing if new else trailing), "removed"


def remove_related_link(text: str, *, target_rel: str) -> tuple[str | None, str]:
    """Remove only the link line(s) in the managed block whose wiki target is ``target_rel``.

    Entry-level (Phase 10G amendment): a valid, non-offending link is never deleted. If removing the
    entry empties the block, the whole block is removed. Returns (new_text|None, reason):
    'removed' | 'emptied_removed' | 'target_not_found' | 'absent' | 'ambiguous_existing_block'.
    """
    stem = target_rel[:-3] if target_rel.endswith(".md") else target_rel
    needle = f"[[{stem}|"
    lines = text.splitlines()
    bounds = _related_block_bounds(lines)
    if bounds is None:
        return text, "absent"
    if bounds == "ambiguous":
        return None, "ambiguous_existing_block"
    bs, be = bounds
    inner = lines[bs + 1:be]
    keep = [ln for ln in inner if needle not in ln]
    if len(keep) == len(inner):
        return text, "target_not_found"
    if not [ln for ln in keep if ln.strip()]:
        new_text, reason = remove_related_block(text)
        return new_text, ("emptied_removed" if reason == "removed" else reason)
    trailing = "\n" if text.endswith("\n") else ""
    new = lines[:bs + 1] + keep + lines[be:]
    return "\n".join(new) + trailing, "removed"


def remove_frontmatter_tags(text: str, tags: list[str]) -> tuple[str | None, str]:
    """Remove specific block-style frontmatter tag lines (exact tag match), preserving all others.

    Returns (new_text|None, reason): 'removed' | 'no_matching_tags' | 'frontmatter_not_block_style'.
    Caller decides WHICH tags to drop (e.g. only graph tags no longer justified by remaining links).
    """
    drop = {(sanitize_tag(t) or t) for t in tags}
    ok, _existing, first, last = parse_frontmatter_tags(text)
    if not ok:
        return None, "frontmatter_not_block_style"
    lines = text.splitlines(keepends=True)
    out, removed = [], 0
    for i, ln in enumerate(lines):
        if first <= i <= last:
            m = re.match(r"^\s*-\s+(.+?)\s*$", ln)
            if m and m.group(1).strip() in drop:
                removed += 1
                continue
        out.append(ln)
    if removed == 0:
        return text, "no_matching_tags"
    return "".join(out), "removed"

