"""N8C-14 citation-safe answer-draft builder — deterministic, source-backed, packet-scoped, NO LLM.

Materializes a bounded, citation-safe DRAFT for ONE N8C-11 research packet by REUSING that packet (never
re-deriving review state or inferring new facts):
  1. ``ResearchPacketRepository.get_research_packet`` + ``list_research_packet_items`` +
     ``list_research_packet_citations`` (all read-only) enumerate the packet's items (each already carrying a
     frozen effective_state / inclusion_state / answer_role / provenance) and their citation manifest;
  2. the packet's ``answer_contract`` GATES the draft: ``answer_allowed=False`` (never assumed True) yields a
     single ``insufficient_support`` section — NEVER a fabricated ``direct_answer``;
  3. otherwise each item is ROUTED to a ``section_type`` by its inclusion_state + the draft-type policy
     (``trusted_answer_draft`` admits only trusted support; ``review_aware_answer_draft`` labels candidates;
     rejected/not_required/superseded and any ``must_not_say`` target → a bounded ``excluded_manifest``);
  4. each answer-support section carries ≥1 citation, preserving the originating ``packet_citation_id`` and
     enriched READ-ONLY with source-connector metadata (``source_ref``/``source_root_key``/``rel_path``) via
     the source index — NEVER a live ``source_file_read``;
  5. the budget caps sections / chars / citations / trusted / candidates / open-questions.

``section_body`` is a bounded restatement assembled ONLY from the packet item's own bounded title / summary /
evidence_excerpt (+ its review label) — no new facts, no bridged gaps. The draft is guidance: there is NO
``final_answer`` / ``answer_text`` / ``generated_answer`` / ``authoritative_answer`` / ``operator_approved_answer``
field anywhere, and nothing is executed. Reads only — it never mutates a packet, projection, review, OR source
table, and never rehydrates a raw source/card/vault/email body. ``preview`` is fully read-only; rows are
persisted only by ``build_answer_draft(apply=True)`` and only into the five N8C-14 draft tables (via the
repository).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from . import answer_draft_models as M
from .context_pack_models import estimate_tokens
from .source_connector_models import SourceConnectorValidationError, encode_source_ref

# Deterministic section ordering (answer first, then caveats/questions, excluded last).
_SECTION_RANK = {
    M.SECTION_DIRECT_ANSWER: 0, M.SECTION_TRUSTED_CONTEXT: 1, M.SECTION_CANDIDATE_CONTEXT: 2,
    M.SECTION_IMPLEMENTATION_NOTE: 3, M.SECTION_SOURCE_SUMMARY: 4, M.SECTION_CAVEAT: 5, M.SECTION_RISK: 6,
    M.SECTION_OPEN_QUESTION: 7, M.SECTION_EXCLUDED_MANIFEST: 8, M.SECTION_UNKNOWN: 9,
}
# Provenance anchors an item/citation may carry, ordered most-specific first, mapped to a citation_type — used
# to synthesize a fallback citation for a support section whose packet item carried no citation manifest.
_ANCHOR_CITATION_TYPES: tuple[tuple[str, str], ...] = (
    ("claim_id", "claim"), ("decision_id", "decision"), ("preference_id", "preference"),
    ("open_loop_id", "open_loop"), ("pack_item_id", "context_pack_item"), ("pack_id", "context_pack_item"),
    ("memory_node_id", "memory"), ("memory_mention_id", "memory"), ("compilation_id", "memory"),
    ("receipt_id", "source"), ("source_id", "source"), ("note_rel_path", "source"),
    ("projection_item_id", "projection_item"), ("review_item_id", "review_item"),
)
_HEX = set("0123456789abcdef")
# Upper bound on the packet-citation manifest scanned per draft (bounds a huge packet).
_CITATION_SCAN = 2_000


@dataclass
class DraftProviders:
    packet_repo: Any                 # research_packet_repository.ResearchPacketRepository
    source_repo: Any = None          # source_index_repository.SourceIndexRepository | None (read-only enrich)


def _answer_allowed(contract: dict[str, Any] | None) -> bool:
    """The contract's derived ``answer_allowed`` is the ONLY gate — defaulting to False when the key is
    missing/ambiguous (never assumed True)."""
    return isinstance(contract, dict) and contract.get("answer_allowed") is True


def _must_not_say_targets(contract: dict[str, Any] | None) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if not isinstance(contract, dict):
        return out
    for e in contract.get("must_not_say") or []:
        if isinstance(e, dict) and e.get("target_id"):
            out.add((e.get("target_kind"), e.get("target_id")))
    return out


def _first_anchor(row: dict[str, Any]) -> tuple[str, str, str]:
    """(citation_type, anchor_kind, anchor_id) for the row's most-specific present provenance anchor."""
    for anchor_kind, citation_type in _ANCHOR_CITATION_TYPES:
        val = row.get(anchor_kind)
        if val:
            return citation_type, anchor_kind, str(val)
    return "unknown", "none", ""


def _enrich_source(source_id: Any, source_repo: Any,
                   conn: sqlite3.Connection | None) -> dict[str, str | None]:
    """Read-only source-connector carry-through: an opaque ``source_ref`` (pure) + indexed
    ``source_root_key``/``rel_path`` (DB read only). NEVER a live file read; ``rel_path`` is relative."""
    sid = str(source_id or "")
    if len(sid) != 32 or any(ch not in _HEX for ch in sid):
        return {"source_ref": None, "source_root_key": None, "rel_path": None}
    try:
        source_ref = encode_source_ref(sid)
    except SourceConnectorValidationError:
        source_ref = None
    root_key = rel_path = None
    if source_repo is not None:
        detail = source_repo.get_source_detail(sid, conn=conn)
        if detail:
            root_key = detail.get("source_root_key")
            rel_path = detail.get("rel_path")
    return {"source_ref": source_ref, "source_root_key": root_key, "rel_path": rel_path}


def _route(item: dict[str, Any], draft_type: str, budget: M.DraftBudget,
           must_not_say: set[tuple[str, str]]) -> dict[str, Any] | None:
    """Decide a section_type + kind for a packet item, honoring draft-type policy + must_not_say. Returns
    None to DROP the item (policy excludes it and the excluded manifest is off/not applicable)."""
    role = item.get("answer_role")
    inc = item.get("inclusion_state")
    tgt = (item.get("target_kind"), item.get("target_id"))
    trusted_only = draft_type == M.TRUSTED_ANSWER_DRAFT

    def excluded() -> dict[str, Any] | None:
        if not budget.include_excluded_manifest:
            return None
        return {"section_type": M.SECTION_EXCLUDED_MANIFEST, "kind": "excluded", "excluded": True}

    # Hard exclusions (rule #5): rejected/not_required/superseded and any must_not_say target never support.
    if inc in M.HARD_EXCLUDE_STATES or role == M.ROLE_EXCLUDED or tgt in must_not_say:
        return excluded()
    if inc == M.INCL_TRUSTED:
        if role == M.ROLE_IMPLEMENTATION:
            st = M.SECTION_IMPLEMENTATION_NOTE
        elif role == M.ROLE_COUNTERPOINT:
            st = M.SECTION_CAVEAT
        elif role == M.ROLE_PRIMARY:
            st = M.SECTION_DIRECT_ANSWER
        else:
            st = M.SECTION_TRUSTED_CONTEXT
        return {"section_type": st, "kind": "trusted", "trusted": True}
    if inc == M.INCL_CANDIDATE:
        if trusted_only or not budget.include_candidates:
            return excluded()
        return {"section_type": M.SECTION_CANDIDATE_CONTEXT, "kind": "candidate", "candidate": True}
    if inc == M.INCL_DEFERRED:
        if trusted_only or not budget.include_deferred:
            return excluded()
        return {"section_type": M.SECTION_OPEN_QUESTION, "kind": "open_question", "open_question": True}
    if inc == M.INCL_STALE:
        if trusted_only or not budget.include_stale:
            return excluded()
        return {"section_type": M.SECTION_RISK, "kind": "caveat"}
    return excluded()


def _section_body(item: dict[str, Any], *, include_evidence: bool, max_chars: int) -> str:
    """Deterministic restatement assembled ONLY from the item's own bounded title/summary/evidence_excerpt.
    No new facts, no gap-bridging."""
    segs = [s for s in (item.get("title"), item.get("summary")) if s]
    if include_evidence and item.get("evidence_excerpt"):
        segs.append(str(item["evidence_excerpt"]))
    return "\n\n".join(str(s) for s in segs)[:max_chars]


def _decide_items(items: list[dict[str, Any]], draft_type: str, budget: M.DraftBudget,
                  must_not_say: set[tuple[str, str]]) -> list[dict[str, Any]]:
    """Route every item, then order deterministically (answer-support first, excluded last)."""
    decided: list[dict[str, Any]] = []
    for item in items:
        route = _route(item, draft_type, budget, must_not_say)
        if route is None:
            continue
        decided.append({"item": item, **route})
    decided.sort(key=lambda d: (_SECTION_RANK.get(d["section_type"], 9),
                                -(d["item"].get("confidence") or 0.0),
                                d["item"].get("target_kind") or "", d["item"].get("target_id") or ""))
    return decided


def _budget_sections(decided: list[dict[str, Any]], *, budget: M.DraftBudget
                     ) -> tuple[list[dict[str, Any]], dict[str, int], bool]:
    """Apply the section budget over the ordered decided entries. Returns kept entries (with section_order +
    bounded body), counts, and truncated."""
    counts = {"trusted": 0, "candidate": 0, "caveat": 0, "open_question": 0, "excluded": 0, "dropped": 0}
    running_chars = 0
    trusted_used = candidate_used = open_q_used = sections_used = 0
    truncated = False
    kept: list[dict[str, Any]] = []

    for d in decided:
        item = d["item"]
        st = d["section_type"]
        kind = d["kind"]
        is_excluded = st == M.SECTION_EXCLUDED_MANIFEST
        drop_reason: str | None = None

        if sections_used >= budget.max_sections:
            drop_reason, truncated = "budget_max_sections", True
        elif kind == "trusted" and budget.max_trusted_sections is not None \
                and trusted_used >= budget.max_trusted_sections:
            drop_reason, truncated = "budget_max_trusted_sections", True
        elif kind == "candidate" and budget.max_candidate_sections is not None \
                and candidate_used >= budget.max_candidate_sections:
            drop_reason, truncated = "budget_max_candidate_sections", True
        elif kind == "open_question" and open_q_used >= budget.max_open_questions:
            drop_reason, truncated = "budget_max_open_questions", True

        # Excluded-manifest entries are content-minimized: heading + label + reason only, no body.
        if is_excluded:
            body = None
        else:
            body = _section_body(item, include_evidence=budget.include_evidence,
                                 max_chars=budget.max_chars_per_section)
            if drop_reason is None and running_chars + len(body) > budget.max_chars:
                drop_reason, truncated = "budget_max_chars", True

        if drop_reason is not None:
            counts["dropped"] += 1
            continue

        sections_used += 1
        if not is_excluded and body:
            running_chars += len(body)
        if kind == "trusted":
            trusted_used += 1
            counts["trusted"] += 1
        elif kind == "candidate":
            candidate_used += 1
            counts["candidate"] += 1
        elif kind == "open_question":
            open_q_used += 1
            counts["open_question"] += 1
        elif kind == "caveat":
            counts["caveat"] += 1
        elif kind == "excluded":
            counts["excluded"] += 1

        kept.append({**d, "section_order": len(kept), "body": body})
    return kept, counts, truncated


def _build_section_and_citations(entry: dict[str, Any], draft_id: str, packet_id: str, *,
                                 grouped: dict[str, list[dict[str, Any]]], budget: M.DraftBudget,
                                 source_repo: Any, citation_budget: list[int],
                                 conn: sqlite3.Connection | None
                                 ) -> tuple[M.AnswerDraftSection, list[M.DraftCitation]]:
    """Realize one draft section + its citations. Every answer-support section is guaranteed ≥1 citation even
    if the global citation budget is exhausted (falling back to the item's own provenance anchor)."""
    item = entry["item"]
    st = entry["section_type"]
    inc = item.get("inclusion_state")
    eff = item.get("effective_state")
    heading = (item.get("title") or item.get("target_id") or st)
    review_label = M.review_label_for(inc, eff)
    section = M.AnswerDraftSection(
        draft_id=draft_id, section_type=st, section_order=entry["section_order"], packet_id=packet_id,
        packet_item_id=item.get("packet_item_id"), answer_role=item.get("answer_role"),
        heading=heading, section_body=entry.get("body"), review_label=review_label,
        effective_state=eff, inclusion_state=inc, confidence=item.get("confidence"),
        trusted=bool(entry.get("trusted")), candidate=bool(entry.get("candidate")),
        open_question=bool(entry.get("open_question")), excluded=bool(entry.get("excluded")),
        target_digest=item.get("target_digest"),
    )
    if st == M.SECTION_EXCLUDED_MANIFEST:
        section.metadata = {"exclusion_reason": item.get("exclusion_reason") or inc}
    section_id = section.section_id()

    citations: list[M.DraftCitation] = []
    source_refs: list[str] = []
    # Excluded manifest carries no citations (content-minimized). Every other section that has an underlying
    # packet item may carry citations; support sections REQUIRE ≥1 (rule #4).
    if st != M.SECTION_EXCLUDED_MANIFEST:
        packet_cites = grouped.get(item.get("packet_item_id") or "", [])
        for order, pc in enumerate(packet_cites):
            if len(citations) >= budget.max_citations_per_section:
                break
            is_first = len(citations) == 0
            if citation_budget[0] <= 0 and not is_first:
                break
            citations.append(_draft_citation_from_packet(pc, draft_id, section_id, packet_id, order,
                                                          source_repo, conn, source_refs))
            citation_budget[0] -= 1
        # Guarantee a citation for support sections that had no packet citation manifest.
        if not citations and M.section_requires_citation(st):
            citations.append(_fallback_citation(item, draft_id, section_id, packet_id, source_repo, conn,
                                                source_refs))
    section.citation_ids = [c.citation_id() for c in citations]
    section.source_refs = source_refs
    if section.section_body:
        section.token_estimate = estimate_tokens(section.section_body)
    return section, citations


def _draft_citation_from_packet(pc: dict[str, Any], draft_id: str, section_id: str, packet_id: str,
                                order: int, source_repo: Any, conn: sqlite3.Connection | None,
                                source_refs: list[str]) -> M.DraftCitation:
    _ctype, anchor_kind, anchor_id = _first_anchor(pc)
    packet_citation_id = pc.get("citation_id")
    if not anchor_id and packet_citation_id:
        anchor_kind, anchor_id = "packet_citation", str(packet_citation_id)
    enrich = _enrich_source(pc.get("source_id"), source_repo, conn)
    if enrich["source_ref"] and enrich["source_ref"] not in source_refs:
        source_refs.append(enrich["source_ref"])
    return M.DraftCitation(
        draft_id=draft_id, draft_section_id=section_id, citation_type=pc.get("citation_type") or "unknown",
        citation_order=order, anchor_kind=anchor_kind, anchor_id=anchor_id, packet_id=packet_id,
        packet_citation_id=packet_citation_id, citation_label=pc.get("label"),
        target_kind=pc.get("target_kind"), target_id=pc.get("target_id"),
        review_item_id=pc.get("review_item_id"), projection_item_id=pc.get("projection_item_id"),
        source_ref=enrich["source_ref"], source_root_key=enrich["source_root_key"],
        rel_path=enrich["rel_path"], source_digest=pc.get("source_digest"),
        card_digest=pc.get("card_digest"), target_digest=pc.get("target_digest"),
        evidence_excerpt=pc.get("evidence_excerpt"), evidence_location=pc.get("evidence_location"),
        confidence=pc.get("confidence"), review_state=pc.get("review_state"),
        effective_state=pc.get("effective_state"), inclusion_state=pc.get("inclusion_state"),
        source_id=pc.get("source_id"), note_rel_path=pc.get("note_rel_path"), claim_id=pc.get("claim_id"),
        receipt_id=pc.get("receipt_id"), pack_id=pc.get("pack_id"), pack_item_id=pc.get("pack_item_id"),
        memory_node_id=pc.get("memory_node_id"), memory_mention_id=pc.get("memory_mention_id"),
        compilation_id=pc.get("compilation_id"), decision_id=pc.get("decision_id"),
        preference_id=pc.get("preference_id"), open_loop_id=pc.get("open_loop_id"),
    )


def _fallback_citation(item: dict[str, Any], draft_id: str, section_id: str, packet_id: str,
                       source_repo: Any, conn: sqlite3.Connection | None,
                       source_refs: list[str]) -> M.DraftCitation:
    """A support section whose packet item carried no citation manifest still gets one citation, synthesized
    from the item's own provenance anchor (packet lineage marked degraded in metadata)."""
    ctype, anchor_kind, anchor_id = _first_anchor(item)
    enrich = _enrich_source(item.get("source_id"), source_repo, conn)
    if enrich["source_ref"] and enrich["source_ref"] not in source_refs:
        source_refs.append(enrich["source_ref"])
    return M.DraftCitation(
        draft_id=draft_id, draft_section_id=section_id, citation_type=ctype, citation_order=0,
        anchor_kind=anchor_kind, anchor_id=anchor_id, packet_id=packet_id, packet_citation_id=None,
        citation_label=f"{ctype}:{anchor_id}", target_kind=item.get("target_kind"),
        target_id=item.get("target_id"), review_item_id=item.get("review_item_id"),
        projection_item_id=item.get("projection_item_id"), source_ref=enrich["source_ref"],
        source_root_key=enrich["source_root_key"], rel_path=enrich["rel_path"],
        source_digest=item.get("source_digest"), card_digest=item.get("card_digest"),
        target_digest=item.get("target_digest"), evidence_excerpt=item.get("evidence_excerpt"),
        evidence_location=item.get("note_rel_path"), confidence=item.get("confidence"),
        effective_state=item.get("effective_state"), inclusion_state=item.get("inclusion_state"),
        source_id=item.get("source_id"), note_rel_path=item.get("note_rel_path"),
        claim_id=item.get("claim_id"), receipt_id=item.get("receipt_id"), pack_id=item.get("pack_id"),
        pack_item_id=item.get("pack_item_id"), memory_node_id=item.get("memory_node_id"),
        memory_mention_id=item.get("memory_mention_id"), compilation_id=item.get("compilation_id"),
        decision_id=item.get("decision_id"), preference_id=item.get("preference_id"),
        open_loop_id=item.get("open_loop_id"),
    )


def _insufficient_support_section(draft_id: str, packet_id: str, contract: dict[str, Any] | None,
                                  header: dict[str, Any]) -> M.AnswerDraftSection:
    """The ONLY section emitted when answer_allowed is False (clarification #5): no fabricated direct answer,
    bounded reason metadata from the answer contract + packet accounting."""
    unresolved = (contract or {}).get("unresolved_questions") or []
    reason = {
        "answer_allowed": False,
        "trusted_count": header.get("trusted_count"),
        "candidate_count": header.get("candidate_count"),
        "excluded_count": header.get("excluded_count"),
        "unresolved_question_count": len(unresolved),
        "must_not_say_count": len((contract or {}).get("must_not_say") or []),
    }
    body = ("No answer can be drafted from this research packet: its answer contract withholds an answer "
            "(answer_allowed=false) — there is no trusted or with-caveat candidate support to cite.")
    return M.AnswerDraftSection(
        draft_id=draft_id, section_type=M.SECTION_INSUFFICIENT_SUPPORT, section_order=0, packet_id=packet_id,
        packet_item_id=None, heading="Insufficient support to draft an answer", section_body=body,
        review_label="insufficient_support", token_estimate=estimate_tokens(body), metadata=reason,
    )


def _item_signals(items: list[dict[str, Any]],
                  grouped: dict[str, list[dict[str, Any]]]) -> list[tuple[str, str, str]]:
    """Per-item (packet_item_id, effective_state, target_digest#citation-lineage-signature). A changed packet
    item, effective state, or citation lineage changes the draft input_digest."""
    signals: list[tuple[str, str, str]] = []
    for item in items:
        pid = item.get("packet_item_id") or ""
        cites = grouped.get(pid, [])
        sig = ";".join(sorted(str(c.get("citation_id") or "") for c in cites))
        signals.append((pid or item.get("target_id") or "", item.get("effective_state") or "",
                        f"{item.get('target_digest') or ''}#{sig}"))
    return signals


def preview_answer_draft(providers: DraftProviders, *, packet_id: str,
                         draft_type: str = M.REVIEW_AWARE_ANSWER_DRAFT,
                         budget: M.DraftBudget | None = None, title: str | None = None,
                         objective: str | None = None, question: str | None = None,
                         created_by: str = "service", limit: int = 200,
                         conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Build a bounded, citation-safe answer DRAFT WITHOUT persisting. Read-only."""
    if draft_type not in M.DRAFT_TYPES:
        raise M.AnswerDraftValidationError(f"unknown_draft_type:{draft_type}")
    budget = (budget or M.DraftBudget.for_type(draft_type)).clamped()
    header = providers.packet_repo.get_research_packet(packet_id, conn=conn)
    if header is None:
        raise M.AnswerDraftValidationError(f"packet_not_found:{packet_id}")

    items = providers.packet_repo.list_research_packet_items(packet_id, included_only=False, limit=limit,
                                                             conn=conn)
    raw_citations = providers.packet_repo.list_research_packet_citations(packet_id, limit=_CITATION_SCAN,
                                                                        conn=conn)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for pc in raw_citations:
        grouped.setdefault(pc.get("packet_item_id") or "", []).append(pc)

    contract: dict[str, Any] | None = None
    if header.get("answer_contract_json"):
        try:
            contract = json.loads(header["answer_contract_json"])
        except (ValueError, TypeError):
            contract = None
    answer_contract_digest = header.get("answer_contract_digest") or ""

    objective = (objective or header.get("objective") or "")[:M.OBJECTIVE_HARD_CAP]
    question = (question or header.get("question") or "")[:M.QUESTION_HARD_CAP]
    draft_policy_json = M.canonical_json({"draft_type": draft_type})
    budget_json = M.canonical_json(budget.to_dict())

    input_digest = M.compute_draft_input_digest(_item_signals(items, grouped), draft_policy_json,
                                                budget_json, answer_contract_digest)
    draft_id = M.compute_draft_id(draft_type, packet_id, objective, question, answer_contract_digest,
                                  draft_policy_json, budget_json, input_digest)

    section_rows: list[dict[str, Any]] = []
    citation_rows: list[dict[str, Any]] = []
    section_ids: list[str] = []
    counts = {"trusted": 0, "candidate": 0, "caveat": 0, "open_question": 0, "excluded": 0, "dropped": 0}
    truncated = False

    if not _answer_allowed(contract):
        # Gate: emit ONLY an insufficient_support section — no fabricated answer, no citations.
        section = _insufficient_support_section(draft_id, packet_id, contract, header)
        row = section.to_row()
        section_rows.append(row)
        section_ids.append(row["draft_section_id"])
    else:
        must_not_say = _must_not_say_targets(contract)
        decided = _decide_items(items, draft_type, budget, must_not_say)
        kept, counts, truncated = _budget_sections(decided, budget=budget)
        citation_budget = [budget.max_citations]
        for entry in kept:
            section, cits = _build_section_and_citations(entry, draft_id, packet_id, grouped=grouped,
                                                         budget=budget, source_repo=providers.source_repo,
                                                         citation_budget=citation_budget, conn=conn)
            row = section.to_row()
            section_rows.append(row)
            section_ids.append(row["draft_section_id"])
            citation_rows.extend(c.to_row() for c in cits)

    output_digest = M.compute_draft_output_digest(section_ids)
    citation_count = len(citation_rows)

    draft = {
        "draft_id": draft_id, "draft_type": draft_type,
        "title": (title or f"{draft_type} for packet {packet_id}")[:M.HEADING_HARD_CAP],
        "objective": objective or None, "question": question or None,
        "packet_id": packet_id, "packet_type": header.get("packet_type"),
        "answer_contract_digest": answer_contract_digest or None,
        "draft_policy_json": draft_policy_json, "budget_json": budget_json, "status": "built",
        "created_by": created_by, "input_digest": input_digest, "output_digest": output_digest,
        "trusted_section_count": counts["trusted"], "candidate_section_count": counts["candidate"],
        "caveat_count": counts["caveat"], "citation_count": citation_count,
        "open_question_count": counts["open_question"], "excluded_count": counts["excluded"],
        "section_count": len(section_rows), "truncated": 1 if truncated else 0,
    }
    receipt = {
        "draft_receipt_id": M.compute_draft_receipt_id(draft_id, input_digest, output_digest,
                                                      answer_contract_digest),
        "draft_id": draft_id, "builder_version": M.ANSWER_DRAFT_BUILDER_VERSION, "packet_id": packet_id,
        "input_digest": input_digest, "output_digest": output_digest,
        "answer_contract_digest": answer_contract_digest or None, "draft_policy_json": draft_policy_json,
        "budget_json": budget_json, "trusted_section_count": counts["trusted"],
        "candidate_section_count": counts["candidate"], "caveat_count": counts["caveat"],
        "citation_count": citation_count, "open_question_count": counts["open_question"],
        "excluded_count": counts["excluded"], "section_count": len(section_rows),
        "dropped_count": counts["dropped"], "truncated": 1 if truncated else 0,
    }
    return {"applied": False, "draft_id": draft_id, "draft": draft, "sections": section_rows,
            "citations": citation_rows, "receipt": receipt, "answer_contract": contract,
            "answer_allowed": _answer_allowed(contract), "counts": counts, "truncated": truncated,
            "input_digest": input_digest, "output_digest": output_digest,
            "section_count": len(section_rows), "citation_count": citation_count}


def build_answer_draft(providers: DraftProviders, repo: Any, *, packet_id: str,
                       draft_type: str = M.REVIEW_AWARE_ANSWER_DRAFT, budget: M.DraftBudget | None = None,
                       apply: bool = False, title: str | None = None, objective: str | None = None,
                       question: str | None = None, created_by: str = "service", limit: int = 200,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Preview, and — only when ``apply`` — persist into the five draft tables (nothing else). Idempotent:
    unchanged inputs create no duplicate; a changed packet/effective-state/citation lineage changes
    ``input_digest`` → a new draft that supersedes the prior one of the same type+packet+policy."""
    preview = preview_answer_draft(providers, packet_id=packet_id, draft_type=draft_type, budget=budget,
                                   title=title, objective=objective, question=question,
                                   created_by=created_by, limit=limit, conn=conn)
    if not apply:
        return preview
    res = repo.upsert_draft(preview["draft"], preview["sections"], preview["citations"],
                            preview["receipt"], conn=conn)
    return {"applied": True, "draft_id": preview["draft_id"], "created": res["created"],
            "reused": res.get("reused", False), "superseded": res.get("superseded", []),
            "answer_allowed": preview["answer_allowed"], "counts": preview["counts"],
            "truncated": preview["truncated"], "section_count": preview["section_count"],
            "citation_count": preview["citation_count"]}


def export_answer_draft(repo: Any, *, draft_id: str, limit: int = 200,
                        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded JSON export of a persisted draft: header + answer contract + bounded sections + bounded
    citations. NO raw source/card/vault/email bodies, no full payloads, no answer prose, no final answer, no
    Markdown/HTML/PDF/doc writer."""
    header = repo.get_answer_draft(draft_id, conn=conn)
    if header is None:
        raise M.AnswerDraftValidationError(f"draft_not_found:{draft_id}")
    sections = repo.list_answer_draft_sections(draft_id, limit=limit, conn=conn)
    citations = repo.list_answer_draft_citations(draft_id, limit=limit, conn=conn)
    return {"format": "json", "draft": header, "sections": sections, "citations": citations,
            "section_count": len(sections), "citation_count": len(citations)}


def mark_answer_draft_stale_if_needed(providers: DraftProviders, repo: Any, *, draft_id: str,
                                      conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Recompute the draft's current input_digest from its packet + policy and, if drifted, mark it stale.
    Draft-owned write only — never mutates the packet/projection/review/source records it reads."""
    header = repo.get_answer_draft(draft_id, conn=conn)
    if header is None:
        return {"draft_id": draft_id, "found": False}
    draft_type = header.get("draft_type")
    packet_id = header.get("packet_id")
    try:
        budget = M.DraftBudget.from_dict(json.loads(header.get("budget_json") or "{}")).clamped()
    except (ValueError, TypeError):
        budget = M.DraftBudget.for_type(draft_type).clamped()
    preview = preview_answer_draft(providers, packet_id=packet_id, draft_type=draft_type, budget=budget,
                                   objective=header.get("objective") or None,
                                   question=header.get("question") or None, conn=conn)
    return repo.mark_answer_draft_stale_if_needed(draft_id, current_input_digest=preview["input_digest"],
                                                  conn=conn)
