"""Models, enums, deterministic identity, budget, answer-role classification, and the answer-context
contract for the N8C-11 review-aware research-packet layer.

Neutral and deterministic (no DB, no vault, no model, NO LLM). Enum tuples are re-exported from the V107
schema module so DB ``CHECK`` constraints and the Python layer can never drift. Text columns are hard-capped
before the repository writes them — a packet item / citation stores only BOUNDED metadata (ids/digests/state
+ bounded title/summary/evidence_excerpt), never a raw source/card/vault body, a raw email body, a full
enrichment ``result_json``, a full context-pack/projection export, a full memory compilation, a full
review-item payload, or a raw prompt/response.

A research packet is a materialized READ product built from N8C-10 projection items. It NEVER generates a
final answer: there is NO ``final_answer`` / ``answer_text`` / ``generated_answer`` / ``response`` field
anywhere. The ``answer_contract`` is guidance METADATA only — it tells a future consumer what may be stated
as trusted, what must be labelled candidate, what must be omitted, that citations are required, and that no
action may be executed. ``answer_allowed`` is COMPUTED from the included support + policy; it is never
defaulted true. Determinism makes rebuilds idempotent; a changed projection item / effective state / citation
digest changes ``input_digest`` and yields a new ``packet_id`` (the prior packet of the same
type+projection+scope is marked stale/superseded by the repository — a packet-owned row only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_research_packet_tables import (
    ANSWER_ROLE_VALUES,
    CITATION_TYPE_VALUES,
    PACKET_EVENT_TYPE_VALUES,
    PACKET_STATUS_VALUES,
    PACKET_TYPE_VALUES,
)

from .memory_models import bound_text, clamp_confidence, sha256_hex

# --- enum re-exports (single source of truth = the schema module) -----------------------
PACKET_TYPES = frozenset(PACKET_TYPE_VALUES)
PACKET_STATUSES = frozenset(PACKET_STATUS_VALUES)
ANSWER_ROLES = frozenset(ANSWER_ROLE_VALUES)
CITATION_TYPES = frozenset(CITATION_TYPE_VALUES)
EVENT_TYPES = frozenset(PACKET_EVENT_TYPE_VALUES)

# Named packet types.
TRUSTED_ANSWER_CONTEXT = "trusted_answer_context"
REVIEW_AWARE_ANSWER_CONTEXT = "review_aware_answer_context"
IMPLEMENTATION_RESEARCH_CONTEXT = "implementation_research_context"
PROJECT_RESEARCH_CONTEXT = "project_research_context"
DECISION_RESEARCH_CONTEXT = "decision_research_context"
OPEN_LOOP_RESEARCH_CONTEXT = "open_loop_research_context"
MEETING_PREP_CONTEXT = "meeting_prep_context"

# Named answer roles.
ROLE_PRIMARY = "primary_support"
ROLE_SUPPORTING = "supporting_context"
ROLE_CANDIDATE = "candidate_context"
ROLE_COUNTERPOINT = "counterpoint"
ROLE_EXCLUDED = "excluded_context"
ROLE_OPEN_QUESTION = "open_question"
ROLE_RISK = "risk_or_caveat"
ROLE_IMPLEMENTATION = "implementation_note"
ROLE_UNKNOWN = "unknown"

# Roles that count as answer SUPPORT (i.e. content a consumer may state, trusted or with-caveat).
_SUPPORT_ROLES = frozenset({ROLE_PRIMARY, ROLE_SUPPORTING, ROLE_CANDIDATE, ROLE_COUNTERPOINT,
                            ROLE_IMPLEMENTATION})

# Inclusion states (carried by projection items) — re-stated as named constants for classification.
INCL_TRUSTED = "trusted"
INCL_CANDIDATE = "candidate"
INCL_EXCLUDED = "excluded"
INCL_STALE = "stale"
INCL_SUPERSEDED = "superseded"
INCL_NOT_REQUIRED = "not_required"
INCL_DEFERRED = "deferred"

# Bump when the packet build/serialization contract changes — folded into the ids.
RESEARCH_PACKET_BUILDER_VERSION = "research-packet-v1"

# --- hard caps --------------------------------------------------------------------------
TITLE_HARD_CAP = 300
SUMMARY_HARD_CAP = 500
EVIDENCE_HARD_CAP = 2_000
OBJECTIVE_HARD_CAP = 500
QUESTION_HARD_CAP = 500
LABEL_HARD_CAP = 200
EVIDENCE_LOCATION_HARD_CAP = 300
MUST_NOT_SAY_ENTRY_CAP = 200          # per-entry bounded, content-minimized
MAX_ITEMS_HARD_CAP = 500
MAX_CITATIONS_HARD_CAP = 2_000
MAX_CITATIONS_PER_ITEM_HARD_CAP = 25
MAX_OPEN_QUESTIONS_HARD_CAP = 100
MUST_NOT_SAY_HARD_CAP = 100
PACK_CHARS_HARD_CAP = 200_000
ITEM_CHARS_HARD_CAP = 8_000


class ResearchPacketValidationError(ValueError):
    """Raised on any structural/size/enum problem before a packet/item/citation row is persisted."""


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def canonical_json(obj: Any) -> str:
    """Deterministic JSON (sorted keys) for scope/policy/budget/contract digests."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"))


# --- budget / policy --------------------------------------------------------------------
@dataclass
class PacketBudget:
    max_items: int = 40
    max_chars: int = 60_000
    max_chars_per_item: int = 4_000
    max_citations: int = 200
    max_citations_per_item: int = 8
    max_trusted: int | None = None
    max_candidates: int | None = None
    max_open_questions: int = 25
    include_candidates: bool = True
    include_deferred: bool = False
    include_stale: bool = False
    include_excluded_manifest: bool = True
    include_evidence: bool = True
    include_metadata: bool = True

    def clamped(self) -> PacketBudget:
        return PacketBudget(
            max_items=_clamp_int(self.max_items, 1, MAX_ITEMS_HARD_CAP, 40),
            max_chars=_clamp_int(self.max_chars, 1, PACK_CHARS_HARD_CAP, 60_000),
            max_chars_per_item=_clamp_int(self.max_chars_per_item, 1, ITEM_CHARS_HARD_CAP, 4_000),
            max_citations=_clamp_int(self.max_citations, 0, MAX_CITATIONS_HARD_CAP, 200),
            max_citations_per_item=_clamp_int(self.max_citations_per_item, 0,
                                              MAX_CITATIONS_PER_ITEM_HARD_CAP, 8),
            max_trusted=(None if self.max_trusted is None
                         else _clamp_int(self.max_trusted, 0, MAX_ITEMS_HARD_CAP, 0)),
            max_candidates=(None if self.max_candidates is None
                            else _clamp_int(self.max_candidates, 0, MAX_ITEMS_HARD_CAP, 0)),
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
            "max_items": self.max_items, "max_chars": self.max_chars,
            "max_chars_per_item": self.max_chars_per_item, "max_citations": self.max_citations,
            "max_citations_per_item": self.max_citations_per_item, "max_trusted": self.max_trusted,
            "max_candidates": self.max_candidates, "max_open_questions": self.max_open_questions,
            "include_candidates": self.include_candidates, "include_deferred": self.include_deferred,
            "include_stale": self.include_stale, "include_excluded_manifest": self.include_excluded_manifest,
            "include_evidence": self.include_evidence, "include_metadata": self.include_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PacketBudget:
        base = cls()
        if not data:
            return base
        return cls(**{k: data.get(k, getattr(base, k)) for k in base.to_dict()})

    @classmethod
    def for_type(cls, packet_type: str, overrides: dict[str, Any] | None = None) -> PacketBudget:
        """Default policy per packet type. ``trusted_answer_context`` excludes candidates by default;
        ``review_aware_answer_context`` includes+labels them; ``implementation_research_context`` includes
        trusted + candidate context but keeps open loops advisory and excludes stale by default."""
        b = cls()
        if packet_type == TRUSTED_ANSWER_CONTEXT:
            b.include_candidates = False
            b.include_deferred = False
            b.include_stale = False
        elif packet_type == IMPLEMENTATION_RESEARCH_CONTEXT:
            b.include_candidates = True
            b.include_stale = False
        else:
            b.include_candidates = True
        merged = {**b.to_dict(), **(overrides or {})}
        return cls.from_dict(merged)


# inclusion_state → (answer_role, default_included_when_policy_allows). ``accepted``→trusted is always
# support; rejected/not_required/superseded are always excluded_context; candidate/deferred/stale are
# policy-gated. ``implementation_research_context`` open loops are relabelled advisory (implementation_note).
def classify_answer_role(inclusion_state: str | None, packet_type: str, budget: PacketBudget,
                         target_kind: str | None = None) -> tuple[str, bool]:
    inc = inclusion_state or INCL_CANDIDATE
    if inc == INCL_TRUSTED:
        role, included = ROLE_PRIMARY, True
    elif inc == INCL_CANDIDATE:
        role, included = ROLE_CANDIDATE, bool(budget.include_candidates)
    elif inc == INCL_DEFERRED:
        role, included = ROLE_OPEN_QUESTION, bool(budget.include_deferred)
    elif inc == INCL_STALE:
        role, included = ROLE_RISK, bool(budget.include_stale)
    elif inc in (INCL_EXCLUDED, INCL_SUPERSEDED, INCL_NOT_REQUIRED):
        role, included = ROLE_EXCLUDED, False
    else:
        role, included = ROLE_UNKNOWN, False
    # Open loops surfaced in an implementation research context are advisory notes — never executable.
    if (packet_type == IMPLEMENTATION_RESEARCH_CONTEXT and target_kind == "open_loop"
            and role in (ROLE_PRIMARY, ROLE_CANDIDATE)):
        role = ROLE_IMPLEMENTATION
    return role, included


def role_is_support(answer_role: str) -> bool:
    return answer_role in _SUPPORT_ROLES


def role_requires_citation(answer_role: str) -> bool:
    """Every included item must be cited UNLESS it is an open question or excluded-context entry."""
    return answer_role not in (ROLE_OPEN_QUESTION, ROLE_EXCLUDED)


# --- answer-context contract (guidance METADATA only — never generated answer content) ---
def build_answer_contract(packet_type: str, budget: PacketBudget, *, trusted_included: int,
                          candidate_included: int, unresolved_questions: list[str],
                          must_not_say: list[str]) -> dict[str, Any]:
    """Compute the answer-context contract. ``answer_allowed`` is DERIVED from the included support: a packet
    whose only support is excluded/stale/superseded/not_required (no included trusted or candidate item)
    yields ``answer_allowed=False``. This is guidance metadata for a downstream consumer — it is NOT an
    answer and contains no answer prose."""
    trusted_allowed = trusted_included > 0
    candidate_allowed = candidate_included > 0 and bool(budget.include_candidates)
    answer_allowed = trusted_allowed or candidate_allowed
    return {
        "answer_allowed": bool(answer_allowed),
        "citation_required": True,
        "review_labels_required": True,
        "trusted_claims_allowed": bool(trusted_allowed),
        "candidate_claims_allowed": ("with_caveat" if candidate_allowed else False),
        "excluded_claims_policy": "omit",
        "open_loops_policy": "advisory_only",
        "action_policy": "no_execution",
        "confidence_policy": "include_effective_state_and_confidence",
        "must_not_say": list(must_not_say),
        "unresolved_questions": list(unresolved_questions),
    }


# --- deterministic identity -------------------------------------------------------------
def compute_answer_contract_digest(answer_contract: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(answer_contract))[:24]


def compute_packet_input_digest(item_signals: list[tuple[str, str, str]], filter_policy_json: str,
                                budget_json: str, answer_contract_digest: str) -> str:
    """Digest over the packet inputs: each item's (projection_item_id, effective_state, combined digest of
    target + its citation signature) sorted, plus policy + budget + answer-contract digest. A changed
    projection item, effective state, or citation digest changes this digest."""
    joined = ";".join(f"{a}|{b}|{c}" for a, b, c in sorted(item_signals))
    return sha256_hex(f"{joined}#pol={filter_policy_json}#bud={budget_json}#ac={answer_contract_digest}")[:24]


def compute_packet_output_digest(included_item_ids: list[str]) -> str:
    return sha256_hex("|".join(sorted(included_item_ids)))[:24]


def compute_packet_id(packet_type: str, projection_id: str, objective: str, question: str,
                      answer_contract_json: str, budget_json: str, input_digest: str) -> str:
    key = (f"{packet_type}|{projection_id}|{objective}|{question}|{answer_contract_json}|{budget_json}|"
           f"{input_digest}|{RESEARCH_PACKET_BUILDER_VERSION}")
    return sha256_hex(key)[:24]


def compute_packet_item_id(packet_id: str, projection_item_id: str | None, answer_role: str,
                           effective_state: str | None, target_digest: str | None) -> str:
    key = (f"{packet_id}|{projection_item_id or ''}|{answer_role}|{effective_state or ''}|"
           f"{target_digest or ''}")
    return sha256_hex(key)[:24]


def compute_citation_id(packet_id: str, packet_item_id: str, citation_type: str,
                        target_kind: str | None, target_id: str | None, anchor_kind: str,
                        anchor_id: str, source_digest: str | None, target_digest: str | None,
                        citation_order: int) -> str:
    """Anchor-specific entropy (anchor_kind + anchor_id + citation_order) is folded in so multiple citations
    for the same target/digest cannot collide."""
    key = (f"{packet_id}|{packet_item_id}|{citation_type}|{target_kind or ''}|{target_id or ''}|"
           f"{anchor_kind}|{anchor_id}|{source_digest or ''}|{target_digest or ''}|{int(citation_order)}")
    return sha256_hex(key)[:24]


def compute_packet_receipt_id(packet_id: str, input_digest: str, output_digest: str,
                              answer_contract_digest: str) -> str:
    return sha256_hex(f"{packet_id}|{input_digest}|{output_digest}|{answer_contract_digest}|"
                      f"{RESEARCH_PACKET_BUILDER_VERSION}")[:24]


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


# --- packet item draft -----------------------------------------------------------------
@dataclass
class ResearchPacketItem:
    packet_id: str
    answer_role: str
    included: bool
    target_kind: str
    target_id: str
    item_order: int = 0
    projection_id: str | None = None
    projection_item_id: str | None = None
    review_item_id: str | None = None
    effective_state: str | None = None
    inclusion_state: str | None = None
    title: str | None = None
    summary: str | None = None
    evidence_excerpt: str | None = None
    confidence: float | None = None
    priority: str | None = None
    token_estimate: int = 0
    exclusion_reason: str | None = None
    citation_ids: list[str] = field(default_factory=list)
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
    source_digest: str | None = None
    card_digest: str | None = None
    target_digest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def _provenance(self) -> dict[str, Any]:
        return {a: getattr(self, a) for a in _ITEM_ANCHORS}

    def to_row(self) -> dict[str, Any]:
        if self.answer_role not in ANSWER_ROLES:
            raise ResearchPacketValidationError(f"unknown_answer_role:{self.answer_role}")
        if not self.target_id:
            raise ResearchPacketValidationError("packet_item_without_target_id")
        if not _has_any(self._provenance(), _ITEM_ANCHORS):
            raise ResearchPacketValidationError("packet_item_without_provenance")
        row = dict(self._provenance())
        row.update({
            "packet_item_id": compute_packet_item_id(self.packet_id, self.projection_item_id,
                                                     self.answer_role, self.effective_state,
                                                     self.target_digest),
            "packet_id": self.packet_id,
            "projection_id": self.projection_id,
            "projection_item_id": self.projection_item_id,
            "item_order": int(self.item_order),
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "review_item_id": self.review_item_id,
            "effective_state": self.effective_state,
            "inclusion_state": self.inclusion_state,
            "answer_role": self.answer_role,
            "title": bound_text(self.title, TITLE_HARD_CAP) if self.title else None,
            "summary": bound_text(self.summary, SUMMARY_HARD_CAP) if self.summary else None,
            "evidence_excerpt": bound_text(self.evidence_excerpt, EVIDENCE_HARD_CAP)
            if self.evidence_excerpt else None,
            "source_digest": self.source_digest,
            "card_digest": self.card_digest,
            "target_digest": self.target_digest,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "priority": self.priority,
            "token_estimate": max(0, int(self.token_estimate)),
            "included": 1 if self.included else 0,
            "exclusion_reason": self.exclusion_reason,
            "citation_ids_json": canonical_json(list(self.citation_ids)) if self.citation_ids else None,
            "metadata_json": (canonical_json(self.metadata) if self.metadata else None),
        })
        return row


# --- citation draft --------------------------------------------------------------------
@dataclass
class Citation:
    packet_id: str
    packet_item_id: str
    citation_type: str
    citation_order: int
    anchor_kind: str
    anchor_id: str
    label: str | None = None
    target_kind: str | None = None
    target_id: str | None = None
    review_item_id: str | None = None
    projection_item_id: str | None = None
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
        return compute_citation_id(self.packet_id, self.packet_item_id, self.citation_type,
                                   self.target_kind, self.target_id, self.anchor_kind, self.anchor_id,
                                   self.source_digest, self.target_digest, self.citation_order)

    def to_row(self) -> dict[str, Any]:
        if self.citation_type not in CITATION_TYPES:
            raise ResearchPacketValidationError(f"unknown_citation_type:{self.citation_type}")
        if not _has_any(self._provenance(), _CITATION_ANCHORS):
            raise ResearchPacketValidationError("citation_without_provenance")
        row = {a: getattr(self, a) for a in _ITEM_ANCHORS}
        row.update({
            "citation_id": self.citation_id(),
            "packet_id": self.packet_id,
            "packet_item_id": self.packet_item_id,
            "citation_order": int(self.citation_order),
            "citation_type": self.citation_type,
            "label": bound_text(self.label, LABEL_HARD_CAP) if self.label else None,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "review_item_id": self.review_item_id,
            "projection_item_id": self.projection_item_id,
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
            "metadata_json": (canonical_json(self.metadata) if self.metadata else None),
        })
        return row


def bound_must_not_say(entries: list[dict[str, Any]], *, cap: int = MUST_NOT_SAY_HARD_CAP) -> list[dict]:
    """Bound + content-minimize the must_not_say manifest: ids / labels / exclusion reasons / short bounded
    summaries only — never full rejected/excluded content."""
    out: list[dict[str, Any]] = []
    for e in entries[:cap]:
        out.append({
            "target_kind": e.get("target_kind"),
            "target_id": e.get("target_id"),
            "effective_state": e.get("effective_state"),
            "inclusion_state": e.get("inclusion_state"),
            "exclusion_reason": e.get("exclusion_reason"),
            "label": bound_text(e.get("label"), MUST_NOT_SAY_ENTRY_CAP) if e.get("label") else None,
        })
    return out
