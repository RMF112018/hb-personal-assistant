"""Models, enums, deterministic identity, budget, section-type classification, and the citation-safe drafting
caps for the N8C-14 answer-draft layer.

Neutral and deterministic (no DB, no vault, no model, NO LLM). Enum tuples are re-exported from the V108
schema module so DB ``CHECK`` constraints and the Python layer can never drift. Text columns are hard-capped
before the repository writes them — a draft section stores only a BOUNDED restatement (``section_body``)
assembled from the packet item's own bounded title/summary/evidence_excerpt + review label, and a draft
citation stores only bounded metadata (ids/labels/digests/state + a bounded evidence excerpt already carried
by the packet citation). Never a raw source/card/vault body, a raw email body, a full packet payload, a full
projection/review payload, or a raw prompt/response.

An answer draft is a materialized, citation-safe READ product built from ONE N8C-11 research packet. It NEVER
generates a final/authoritative answer: there is NO ``final_answer`` / ``answer_text`` / ``generated_answer`` /
``authoritative_answer`` / ``operator_approved_answer`` field anywhere. ``section_body`` is bounded DRAFT text
only — guidance a downstream consumer may read, never operator-approved truth. Determinism makes rebuilds
idempotent; a changed packet item / effective state / citation lineage changes ``input_digest`` and yields a
new ``draft_id`` (the prior draft of the same type+packet+policy is marked stale/superseded by the repository —
a draft-owned row only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_answer_draft_tables import (
    CITATION_TYPE_VALUES,
    DRAFT_STATUS_VALUES,
    DRAFT_TYPE_VALUES,
    PACKET_EVENT_TYPE_VALUES,
    SECTION_TYPE_VALUES,
)

from .memory_models import bound_text, clamp_confidence, sha256_hex

# --- enum re-exports (single source of truth = the schema module) -----------------------
DRAFT_TYPES = frozenset(DRAFT_TYPE_VALUES)
DRAFT_STATUSES = frozenset(DRAFT_STATUS_VALUES)
SECTION_TYPES = frozenset(SECTION_TYPE_VALUES)
CITATION_TYPES = frozenset(CITATION_TYPE_VALUES)
EVENT_TYPES = frozenset(PACKET_EVENT_TYPE_VALUES)

# Named draft types.
TRUSTED_ANSWER_DRAFT = "trusted_answer_draft"
REVIEW_AWARE_ANSWER_DRAFT = "review_aware_answer_draft"
IMPLEMENTATION_CONTEXT_DRAFT = "implementation_context_draft"
MEETING_PREP_DRAFT = "meeting_prep_draft"
PROJECT_RESEARCH_DRAFT = "project_research_draft"
OPEN_LOOP_SUMMARY_DRAFT = "open_loop_summary_draft"

# Named section types.
SECTION_DIRECT_ANSWER = "direct_answer"
SECTION_TRUSTED_CONTEXT = "trusted_context"
SECTION_CANDIDATE_CONTEXT = "candidate_context"
SECTION_CAVEAT = "caveat"
SECTION_OPEN_QUESTION = "open_question"
SECTION_RISK = "risk"
SECTION_SOURCE_SUMMARY = "source_summary"
SECTION_IMPLEMENTATION_NOTE = "implementation_note"
SECTION_EXCLUDED_MANIFEST = "excluded_manifest"
SECTION_INSUFFICIENT_SUPPORT = "insufficient_support"
SECTION_UNKNOWN = "unknown"

# Named answer roles (carried by packet items) — re-stated for classification/routing.
ROLE_PRIMARY = "primary_support"
ROLE_SUPPORTING = "supporting_context"
ROLE_CANDIDATE = "candidate_context"
ROLE_COUNTERPOINT = "counterpoint"
ROLE_EXCLUDED = "excluded_context"
ROLE_OPEN_QUESTION = "open_question"
ROLE_RISK = "risk_or_caveat"
ROLE_IMPLEMENTATION = "implementation_note"
ROLE_UNKNOWN = "unknown"

# Inclusion states (carried by packet items) — re-stated as named constants for routing/flags.
INCL_TRUSTED = "trusted"
INCL_CANDIDATE = "candidate"
INCL_EXCLUDED = "excluded"
INCL_STALE = "stale"
INCL_SUPERSEDED = "superseded"
INCL_NOT_REQUIRED = "not_required"
INCL_DEFERRED = "deferred"

# Section types that are answer SUPPORT — each MUST carry ≥1 citation (rule #4). open_question / caveat /
# risk / excluded_manifest / insufficient_support / unknown may omit citations.
ANSWER_SUPPORT_SECTION_TYPES = frozenset({
    SECTION_DIRECT_ANSWER, SECTION_TRUSTED_CONTEXT, SECTION_CANDIDATE_CONTEXT,
    SECTION_SOURCE_SUMMARY, SECTION_IMPLEMENTATION_NOTE,
})

# Inclusion states that are NEVER answer-support regardless of policy → routed to the bounded
# excluded_manifest and folded into the answer_contract's must_not_say set.
HARD_EXCLUDE_STATES = frozenset({INCL_EXCLUDED, INCL_NOT_REQUIRED, INCL_SUPERSEDED})

# Bump when the draft build/serialization contract changes — folded into the ids.
ANSWER_DRAFT_BUILDER_VERSION = "answer-draft-v1"

# --- hard caps --------------------------------------------------------------------------
HEADING_HARD_CAP = 300
BODY_HARD_CAP = 2_000
REVIEW_LABEL_HARD_CAP = 200
OBJECTIVE_HARD_CAP = 500
QUESTION_HARD_CAP = 500
LABEL_HARD_CAP = 200
EVIDENCE_HARD_CAP = 2_000
EVIDENCE_LOCATION_HARD_CAP = 300
SOURCE_REF_CAP = 400
REL_PATH_CAP = 500
MAX_SECTIONS_HARD_CAP = 500
MAX_CITATIONS_HARD_CAP = 2_000
MAX_CITATIONS_PER_SECTION_HARD_CAP = 25
MAX_OPEN_QUESTIONS_HARD_CAP = 100
MAX_SOURCE_REFS_PER_SECTION = 25
DRAFT_CHARS_HARD_CAP = 200_000
SECTION_CHARS_HARD_CAP = 8_000


class AnswerDraftValidationError(ValueError):
    """Raised on any structural/size/enum problem before a draft/section/citation row is persisted."""


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def canonical_json(obj: Any) -> str:
    """Deterministic JSON (sorted keys) for policy/budget/contract digests."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"))


# --- budget / policy --------------------------------------------------------------------
@dataclass
class DraftBudget:
    max_sections: int = 40
    max_chars: int = 60_000
    max_chars_per_section: int = 2_000
    max_citations: int = 200
    max_citations_per_section: int = 8
    max_trusted_sections: int | None = None
    max_candidate_sections: int | None = None
    max_open_questions: int = 25
    include_candidates: bool = True
    include_deferred: bool = False
    include_stale: bool = False
    include_excluded_manifest: bool = True
    include_evidence: bool = True
    include_metadata: bool = True

    def clamped(self) -> DraftBudget:
        return DraftBudget(
            max_sections=_clamp_int(self.max_sections, 1, MAX_SECTIONS_HARD_CAP, 40),
            max_chars=_clamp_int(self.max_chars, 1, DRAFT_CHARS_HARD_CAP, 60_000),
            max_chars_per_section=_clamp_int(self.max_chars_per_section, 1, SECTION_CHARS_HARD_CAP, 2_000),
            max_citations=_clamp_int(self.max_citations, 0, MAX_CITATIONS_HARD_CAP, 200),
            max_citations_per_section=_clamp_int(self.max_citations_per_section, 0,
                                                 MAX_CITATIONS_PER_SECTION_HARD_CAP, 8),
            max_trusted_sections=(None if self.max_trusted_sections is None
                                  else _clamp_int(self.max_trusted_sections, 0, MAX_SECTIONS_HARD_CAP, 0)),
            max_candidate_sections=(None if self.max_candidate_sections is None
                                    else _clamp_int(self.max_candidate_sections, 0, MAX_SECTIONS_HARD_CAP, 0)),
            max_open_questions=_clamp_int(self.max_open_questions, 0, MAX_OPEN_QUESTIONS_HARD_CAP, 25),
            include_candidates=bool(self.include_candidates),
            include_deferred=bool(self.include_deferred),
            include_stale=bool(self.include_stale),
            include_excluded_manifest=bool(self.include_excluded_manifest),
            include_evidence=bool(self.include_evidence),
            include_metadata=bool(self.include_metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_sections": self.max_sections, "max_chars": self.max_chars,
            "max_chars_per_section": self.max_chars_per_section, "max_citations": self.max_citations,
            "max_citations_per_section": self.max_citations_per_section,
            "max_trusted_sections": self.max_trusted_sections,
            "max_candidate_sections": self.max_candidate_sections,
            "max_open_questions": self.max_open_questions, "include_candidates": self.include_candidates,
            "include_deferred": self.include_deferred, "include_stale": self.include_stale,
            "include_excluded_manifest": self.include_excluded_manifest,
            "include_evidence": self.include_evidence, "include_metadata": self.include_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DraftBudget:
        base = cls()
        if not data:
            return base
        return cls(**{k: data.get(k, getattr(base, k)) for k in base.to_dict()})

    @classmethod
    def for_type(cls, draft_type: str, overrides: dict[str, Any] | None = None) -> DraftBudget:
        """Default policy per draft type. ``trusted_answer_draft`` excludes candidates by default;
        ``review_aware_answer_draft`` includes+labels them; ``implementation_context_draft`` includes trusted
        + candidate context but keeps open loops advisory and excludes stale by default."""
        b = cls()
        if draft_type == TRUSTED_ANSWER_DRAFT:
            b.include_candidates = False
            b.include_deferred = False
            b.include_stale = False
        elif draft_type == IMPLEMENTATION_CONTEXT_DRAFT:
            b.include_candidates = True
            b.include_stale = False
        else:
            b.include_candidates = True
        merged = {**b.to_dict(), **(overrides or {})}
        return cls.from_dict(merged)


# --- section-type classification --------------------------------------------------------
# answer_role → base section_type (before draft-type gating in the builder). primary_support→direct_answer,
# supporting_context→trusted_context, candidate_context→candidate_context, counterpoint→caveat,
# risk_or_caveat→risk, open_question→open_question, implementation_note→implementation_note,
# excluded_context→excluded_manifest, unknown→unknown.
_ROLE_TO_SECTION = {
    ROLE_PRIMARY: SECTION_DIRECT_ANSWER,
    ROLE_SUPPORTING: SECTION_TRUSTED_CONTEXT,
    ROLE_CANDIDATE: SECTION_CANDIDATE_CONTEXT,
    ROLE_COUNTERPOINT: SECTION_CAVEAT,
    ROLE_RISK: SECTION_RISK,
    ROLE_OPEN_QUESTION: SECTION_OPEN_QUESTION,
    ROLE_IMPLEMENTATION: SECTION_IMPLEMENTATION_NOTE,
    ROLE_EXCLUDED: SECTION_EXCLUDED_MANIFEST,
    ROLE_UNKNOWN: SECTION_UNKNOWN,
}


def classify_section_type(answer_role: str | None, draft_type: str) -> str:
    """Map a packet item's ``answer_role`` to a base ``section_type``. Draft-type gating (trusted-only, must
    not say, budget) is applied by the builder on top of this base."""
    return _ROLE_TO_SECTION.get(answer_role or ROLE_UNKNOWN, SECTION_UNKNOWN)


def section_requires_citation(section_type: str) -> bool:
    """Every answer-support section must carry ≥1 citation; open_question / caveat / risk / excluded_manifest /
    insufficient_support / unknown may omit."""
    return section_type in ANSWER_SUPPORT_SECTION_TYPES


def review_label_for(inclusion_state: str | None, effective_state: str | None) -> str:
    """Deterministic visible review label from the item's frozen inclusion/effective state — never fabricated
    prose. e.g. ``trusted`` → "trusted"; ``candidate`` → "candidate — review required"."""
    inc = inclusion_state or "unknown"
    if inc == INCL_TRUSTED:
        return "trusted"
    if inc == INCL_CANDIDATE:
        return "candidate — review required"
    if inc == INCL_DEFERRED:
        return "deferred — open question"
    if inc == INCL_STALE:
        return "stale — verify before use"
    if inc == INCL_EXCLUDED:
        return "excluded — rejected"
    if inc == INCL_NOT_REQUIRED:
        return "excluded — not required"
    if inc == INCL_SUPERSEDED:
        return "excluded — superseded"
    return f"state:{inc}" + (f"/{effective_state}" if effective_state else "")


# --- deterministic identity -------------------------------------------------------------
def compute_draft_input_digest(section_signals: list[tuple[str, str, str]], draft_policy_json: str,
                               budget_json: str, answer_contract_digest: str) -> str:
    """Digest over the draft inputs: each packet item's (packet_item_id, effective_state, combined digest of
    target + its citation lineage signature) sorted, plus policy + budget + answer-contract digest. A changed
    packet item, effective state, or citation lineage changes this digest."""
    joined = ";".join(f"{a}|{b}|{c}" for a, b, c in sorted(section_signals))
    return sha256_hex(f"{joined}#pol={draft_policy_json}#bud={budget_json}#ac={answer_contract_digest}")[:24]


def compute_draft_output_digest(section_ids: list[str]) -> str:
    return sha256_hex("|".join(sorted(section_ids)))[:24]


def compute_draft_id(draft_type: str, packet_id: str, objective: str, question: str,
                     answer_contract_digest: str, draft_policy_json: str, budget_json: str,
                     input_digest: str) -> str:
    key = (f"{draft_type}|{packet_id}|{objective}|{question}|{answer_contract_digest}|{draft_policy_json}|"
           f"{budget_json}|{input_digest}|{ANSWER_DRAFT_BUILDER_VERSION}")
    return sha256_hex(key)[:24]


def compute_draft_section_id(draft_id: str, packet_item_id: str | None, section_type: str,
                             effective_state: str | None, section_order: int) -> str:
    key = (f"{draft_id}|{packet_item_id or ''}|{section_type}|{effective_state or ''}|{int(section_order)}")
    return sha256_hex(key)[:24]


def compute_draft_citation_id(draft_id: str, draft_section_id: str, citation_type: str,
                              packet_citation_id: str | None, anchor_kind: str, anchor_id: str,
                              citation_order: int) -> str:
    """Anchor-specific entropy (packet_citation_id or anchor_kind+anchor_id, plus citation_order) is folded in
    so two citations on the same section cannot collide."""
    key = (f"{draft_id}|{draft_section_id}|{citation_type}|{packet_citation_id or ''}|{anchor_kind}|"
           f"{anchor_id}|{int(citation_order)}")
    return sha256_hex(key)[:24]


def compute_draft_receipt_id(draft_id: str, input_digest: str, output_digest: str,
                             answer_contract_digest: str) -> str:
    return sha256_hex(f"{draft_id}|{input_digest}|{output_digest}|{answer_contract_digest}|"
                      f"{ANSWER_DRAFT_BUILDER_VERSION}")[:24]


# --- provenance ------------------------------------------------------------------------
_ITEM_ANCHORS = (
    "source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
    "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id",
    "open_loop_id",
)
# Citations may also be anchored purely by a review item or a projection item.
_CITATION_ANCHORS = (*_ITEM_ANCHORS, "review_item_id", "projection_item_id")


def _has_any(provenance: dict[str, Any], anchors: tuple[str, ...]) -> bool:
    return any(provenance.get(a) for a in anchors)


# --- draft section ---------------------------------------------------------------------
@dataclass
class AnswerDraftSection:
    draft_id: str
    section_type: str
    section_order: int = 0
    packet_id: str | None = None
    packet_item_id: str | None = None
    answer_role: str | None = None
    heading: str | None = None
    section_body: str | None = None
    review_label: str | None = None
    effective_state: str | None = None
    inclusion_state: str | None = None
    confidence: float | None = None
    citation_ids: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    trusted: bool = False
    candidate: bool = False
    open_question: bool = False
    excluded: bool = False
    token_estimate: int = 0
    target_digest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def section_id(self) -> str:
        return compute_draft_section_id(self.draft_id, self.packet_item_id, self.section_type,
                                        self.effective_state, self.section_order)

    def to_row(self) -> dict[str, Any]:
        if self.section_type not in SECTION_TYPES:
            raise AnswerDraftValidationError(f"unknown_section_type:{self.section_type}")
        if self.answer_role is not None and self.answer_role not in _ROLE_TO_SECTION:
            raise AnswerDraftValidationError(f"unknown_answer_role:{self.answer_role}")
        body = bound_text(self.section_body, BODY_HARD_CAP) if self.section_body else None
        source_refs = [bound_text(r, SOURCE_REF_CAP) for r in self.source_refs[:MAX_SOURCE_REFS_PER_SECTION]]
        return {
            "draft_section_id": self.section_id(),
            "draft_id": self.draft_id,
            "packet_id": self.packet_id,
            "packet_item_id": self.packet_item_id,
            "section_order": int(self.section_order),
            "section_type": self.section_type,
            "heading": bound_text(self.heading, HEADING_HARD_CAP) if self.heading else None,
            "section_body": body,
            "review_label": bound_text(self.review_label, REVIEW_LABEL_HARD_CAP)
            if self.review_label else None,
            "effective_state": self.effective_state,
            "inclusion_state": self.inclusion_state,
            "answer_role": self.answer_role,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "citation_ids_json": canonical_json(list(self.citation_ids)) if self.citation_ids else None,
            "source_refs_json": canonical_json(source_refs) if source_refs else None,
            "trusted": 1 if self.trusted else 0,
            "candidate": 1 if self.candidate else 0,
            "open_question": 1 if self.open_question else 0,
            "excluded": 1 if self.excluded else 0,
            "token_estimate": max(0, int(self.token_estimate)),
            "char_count": len(body) if body else 0,
            "metadata_json": (canonical_json(self.metadata) if self.metadata else None),
        }


# --- draft citation --------------------------------------------------------------------
@dataclass
class DraftCitation:
    draft_id: str
    draft_section_id: str
    citation_type: str
    citation_order: int
    anchor_kind: str
    anchor_id: str
    packet_id: str | None = None
    packet_citation_id: str | None = None
    citation_label: str | None = None
    target_kind: str | None = None
    target_id: str | None = None
    review_item_id: str | None = None
    projection_item_id: str | None = None
    source_ref: str | None = None
    source_root_key: str | None = None
    rel_path: str | None = None
    source_digest: str | None = None
    card_digest: str | None = None
    target_digest: str | None = None
    evidence_excerpt: str | None = None
    evidence_location: str | None = None
    confidence: float | None = None
    review_state: str | None = None
    effective_state: str | None = None
    inclusion_state: str | None = None
    # provenance
    source_id: str | None = None
    note_rel_path: str | None = None
    claim_id: str | None = None
    receipt_id: str | None = None
    pack_id: str | None = None
    pack_item_id: str | None = None
    memory_node_id: str | None = None
    memory_mention_id: str | None = None
    compilation_id: str | None = None
    decision_id: str | None = None
    preference_id: str | None = None
    open_loop_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def _provenance(self) -> dict[str, Any]:
        prov = {a: getattr(self, a) for a in _ITEM_ANCHORS}
        prov["review_item_id"] = self.review_item_id
        prov["projection_item_id"] = self.projection_item_id
        return prov

    def citation_id(self) -> str:
        return compute_draft_citation_id(self.draft_id, self.draft_section_id, self.citation_type,
                                         self.packet_citation_id, self.anchor_kind, self.anchor_id,
                                         self.citation_order)

    def to_row(self) -> dict[str, Any]:
        if self.citation_type not in CITATION_TYPES:
            raise AnswerDraftValidationError(f"unknown_citation_type:{self.citation_type}")
        # Preserve packet_citation_id whenever available; otherwise require ≥1 provenance anchor and mark the
        # citation lineage degraded in metadata (clarification #6).
        metadata = dict(self.metadata)
        if not self.packet_citation_id:
            if not _has_any(self._provenance(), _CITATION_ANCHORS):
                raise AnswerDraftValidationError("citation_without_packet_lineage_or_provenance")
            metadata.setdefault("citation_lineage", "degraded")
        row = {a: getattr(self, a) for a in _ITEM_ANCHORS}
        row.update({
            "draft_citation_id": self.citation_id(),
            "draft_id": self.draft_id,
            "draft_section_id": self.draft_section_id,
            "packet_id": self.packet_id,
            "packet_citation_id": self.packet_citation_id,
            "citation_order": int(self.citation_order),
            "citation_type": self.citation_type,
            "citation_label": bound_text(self.citation_label, LABEL_HARD_CAP)
            if self.citation_label else None,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "review_item_id": self.review_item_id,
            "projection_item_id": self.projection_item_id,
            "source_ref": bound_text(self.source_ref, SOURCE_REF_CAP) if self.source_ref else None,
            "source_root_key": self.source_root_key,
            "rel_path": bound_text(self.rel_path, REL_PATH_CAP) if self.rel_path else None,
            "source_digest": self.source_digest,
            "card_digest": self.card_digest,
            "target_digest": self.target_digest,
            "evidence_excerpt": bound_text(self.evidence_excerpt, EVIDENCE_HARD_CAP)
            if self.evidence_excerpt else None,
            "evidence_location": bound_text(self.evidence_location, EVIDENCE_LOCATION_HARD_CAP)
            if self.evidence_location else None,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "review_state": self.review_state,
            "effective_state": self.effective_state,
            "inclusion_state": self.inclusion_state,
            "metadata_json": (canonical_json(metadata) if metadata else None),
        })
        return row
