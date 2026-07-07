"""N8C-11 review-aware research-packet builder — deterministic, source-backed, projection-scoped, NO LLM.

Materializes a bounded, citation-backed, answer-CONTEXT packet for ONE N8C-10 intelligence projection by
REUSING that projection (never re-deriving review state):
  1. ``IntelligenceProjectionRepository.get_projection`` + ``list_projection_items`` (read-only) enumerate the
     projection's items, each already carrying a frozen effective_state / inclusion_state / provenance anchors
     / digests;
  2. ``classify_answer_role`` maps each item's inclusion_state → an ``answer_role`` per the packet type's
     policy;
  3. a citation is emitted per provenance anchor (every included non-open-question/excluded item is cited);
  4. the budget caps items / chars / citations / trusted / candidates / open-questions;
  5. an answer-context CONTRACT (guidance metadata only — no answer prose) is computed, with ``answer_allowed``
     DERIVED from the included support.

Reads only — it never mutates a source advisory, review, OR projection table, never converts a candidate into
accepted truth, generates NO final answer, and executes nothing. It does NOT rehydrate raw source/card/vault/
email bodies — it only copies the bounded excerpts already carried by the projection items. ``preview`` is
fully read-only; rows are persisted only by ``build_research_packet(apply=True)`` and only into the five
N8C-11 packet tables (via the repository).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from . import research_packet_models as M
from .context_pack_models import estimate_tokens

# Deterministic answer-role ordering (support first, then caveats/questions, excluded last).
_ROLE_RANK = {
    M.ROLE_PRIMARY: 0, M.ROLE_SUPPORTING: 1, M.ROLE_CANDIDATE: 2, M.ROLE_IMPLEMENTATION: 3,
    M.ROLE_COUNTERPOINT: 4, M.ROLE_RISK: 5, M.ROLE_OPEN_QUESTION: 6, M.ROLE_EXCLUDED: 7,
    M.ROLE_UNKNOWN: 8,
}
# inclusion_state → hard exclusion reason (states that are never answer-support regardless of policy).
_HARD_EXCLUDE_REASON = {
    M.INCL_EXCLUDED: "rejected", M.INCL_NOT_REQUIRED: "not_required", M.INCL_SUPERSEDED: "superseded",
}
# Provenance anchor → citation_type, ordered most-specific first. The projection_item/review_item anchors
# are always-available fallbacks so every item can be cited.
_ANCHOR_CITATION_TYPES: tuple[tuple[str, str], ...] = (
    ("claim_id", "claim"),
    ("decision_id", "decision"),
    ("preference_id", "preference"),
    ("open_loop_id", "open_loop"),
    ("pack_item_id", "context_pack_item"),
    ("pack_id", "context_pack_item"),
    ("memory_node_id", "memory"),
    ("memory_mention_id", "memory"),
    ("compilation_id", "memory"),
    ("receipt_id", "source"),
    ("source_id", "source"),
    ("note_rel_path", "source"),
    ("projection_item_id", "projection_item"),
    ("review_item_id", "review_item"),
)
# Inclusion states that feed the must_not_say manifest.
_MUST_NOT_SAY_STATES = frozenset({M.INCL_EXCLUDED, M.INCL_NOT_REQUIRED, M.INCL_SUPERSEDED})


@dataclass
class PacketProviders:
    projection_repo: Any        # intelligence_projection_repository.IntelligenceProjectionRepository


def _anchor_candidates(item: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Ordered (citation_type, anchor_kind, anchor_id) tuples for the item's present provenance anchors."""
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for anchor_kind, citation_type in _ANCHOR_CITATION_TYPES:
        val = item.get(anchor_kind)
        if val and (citation_type, str(val)) not in seen:
            seen.add((citation_type, str(val)))
            out.append((citation_type, anchor_kind, str(val)))
    return out


def _citation_signature(candidates: list[tuple[str, str, str]]) -> str:
    """Stable signature over an item's anchor set (independent of packet_id) so a changed anchor set changes
    the packet input_digest."""
    return ";".join(sorted(f"{ak}={aid}" for _t, ak, aid in candidates))


def _classify(providers: PacketProviders, *, projection_id: str, packet_type: str,
              budget: M.PacketBudget, limit: int,
              conn: sqlite3.Connection | None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Read-only: load the projection + its items, map each to an answer_role. No writes."""
    header = providers.projection_repo.get_projection(projection_id, conn=conn)
    if header is None:
        return None, []
    rows = providers.projection_repo.list_projection_items(projection_id, included_only=False,
                                                           limit=limit, conn=conn)
    out: list[dict[str, Any]] = []
    for row in rows:
        inc = row.get("inclusion_state")
        role, policy_included = M.classify_answer_role(inc, packet_type, budget, row.get("target_kind"))
        cands = _anchor_candidates(row)
        out.append({"row": row, "answer_role": role, "policy_included": policy_included,
                    "candidates": cands, "citation_signature": _citation_signature(cands)})
    out.sort(key=lambda x: (_ROLE_RANK.get(x["answer_role"], 9),
                            -(x["row"].get("confidence") or 0.0),
                            x["row"].get("target_kind") or "", x["row"].get("target_id") or ""))
    return header, out


def _budget_items(classified: list[dict[str, Any]], *, budget: M.PacketBudget
                  ) -> tuple[list[dict[str, Any]], dict[str, int], bool]:
    """Apply the item budget over the ordered classified items. Returns decorated entries (with included /
    exclusion_reason / bounded text / token estimate), counts, and truncated."""
    counts = {"trusted": 0, "candidate": 0, "excluded": 0, "open_question": 0, "dropped": 0,
              "manifest": 0}
    running_chars = 0
    trusted_used = candidate_used = items_used = open_q_used = manifest_used = 0
    truncated = False
    decorated: list[dict[str, Any]] = []

    for order, c in enumerate(classified):
        row = c["row"]
        role = c["answer_role"]
        inc = row.get("inclusion_state")
        title = row.get("title")
        summary = row.get("summary")
        evidence = row.get("evidence_excerpt") if budget.include_evidence else None
        included = False
        reason: str | None = None
        token_est = 0

        if not c["policy_included"]:
            reason = _HARD_EXCLUDE_REASON.get(inc, f"policy_{inc or 'unknown'}")
        elif role == M.ROLE_OPEN_QUESTION and open_q_used >= budget.max_open_questions:
            reason, truncated = "budget_max_open_questions", True
        elif inc == M.INCL_TRUSTED and budget.max_trusted is not None and trusted_used >= budget.max_trusted:
            reason, truncated = "budget_max_trusted", True
        elif inc == M.INCL_CANDIDATE and budget.max_candidates is not None \
                and candidate_used >= budget.max_candidates:
            reason, truncated = "budget_max_candidates", True
        elif items_used >= budget.max_items:
            reason, truncated = "budget_max_items", True
        else:
            ev = (evidence or "")[: budget.max_chars_per_item] if evidence else None
            content = f"{title or ''}{summary or ''}{ev or ''}"
            if running_chars + len(content) > budget.max_chars:
                reason, truncated = "budget_max_chars", True
            else:
                included = True
                evidence = ev
                running_chars += len(content)
                items_used += 1
                if inc == M.INCL_TRUSTED:
                    trusted_used += 1
                elif inc == M.INCL_CANDIDATE:
                    candidate_used += 1
                if role == M.ROLE_OPEN_QUESTION:
                    open_q_used += 1
                token_est = estimate_tokens(f"{title or ''} {summary or ''}") + estimate_tokens(evidence)

        # Excluded items keep ids/state/digests/exclusion_reason but carry no unnecessary content.
        if not included:
            # Bound the exclusion manifest itself so a huge projection can't blow the packet up.
            if not budget.include_excluded_manifest or manifest_used >= budget.max_items:
                if reason and reason.startswith("budget_"):
                    counts["dropped"] += 1
                continue
            manifest_used += 1
            counts["manifest"] += 1
            summary = None
            evidence = None
            if reason and reason.startswith("budget_"):
                counts["dropped"] += 1

        if included:
            if inc == M.INCL_TRUSTED:
                counts["trusted"] += 1
            elif inc == M.INCL_CANDIDATE:
                counts["candidate"] += 1
            if role == M.ROLE_OPEN_QUESTION:
                counts["open_question"] += 1
        if inc in _MUST_NOT_SAY_STATES:
            counts["excluded"] += 1

        decorated.append({**c, "included": included, "exclusion_reason": reason, "item_order": order,
                          "title": title, "summary": summary, "evidence": evidence,
                          "token_estimate": token_est})
    return decorated, counts, truncated


def _build_item_and_citations(entry: dict[str, Any], packet_id: str, projection_id: str, *,
                              budget: M.PacketBudget, citation_budget: list[int]
                              ) -> tuple[M.ResearchPacketItem, list[M.Citation]]:
    """Realize one packet item + its citations. ``citation_budget`` is a 1-element mutable global counter
    (remaining citations). Every included non-open-question/excluded item is guaranteed at least one
    citation even if the global budget is exhausted."""
    row = entry["row"]
    role = entry["answer_role"]
    item = M.ResearchPacketItem(
        packet_id=packet_id, answer_role=role, included=entry["included"],
        target_kind=row.get("target_kind"), target_id=row.get("target_id"),
        item_order=entry["item_order"], projection_id=projection_id,
        projection_item_id=row.get("projection_item_id"), review_item_id=row.get("review_item_id"),
        effective_state=row.get("effective_state"), inclusion_state=row.get("inclusion_state"),
        title=entry["title"], summary=entry["summary"], evidence_excerpt=entry["evidence"],
        confidence=row.get("confidence"), priority=row.get("priority"),
        token_estimate=entry["token_estimate"], exclusion_reason=entry["exclusion_reason"],
        source_id=row.get("source_id"), note_rel_path=row.get("note_rel_path"),
        claim_id=row.get("claim_id"), receipt_id=row.get("receipt_id"), pack_id=row.get("pack_id"),
        pack_item_id=row.get("pack_item_id"), memory_node_id=row.get("memory_node_id"),
        memory_mention_id=row.get("memory_mention_id"), compilation_id=row.get("compilation_id"),
        decision_id=row.get("decision_id"), preference_id=row.get("preference_id"),
        open_loop_id=row.get("open_loop_id"), source_digest=row.get("source_digest"),
        card_digest=row.get("card_digest"), target_digest=row.get("target_digest"),
    )
    packet_item_id = M.compute_packet_item_id(packet_id, row.get("projection_item_id"), role,
                                              row.get("effective_state"), row.get("target_digest"))
    citations: list[M.Citation] = []
    # Only included items that require citation get a manifest; open questions / excluded context do not.
    if entry["included"] and M.role_requires_citation(role):
        for cite_type, anchor_kind, anchor_id in entry["candidates"]:
            if len(citations) >= budget.max_citations_per_item:
                break
            is_first = len(citations) == 0
            if citation_budget[0] <= 0 and not is_first:
                break  # global cap reached — but always guarantee the first citation
            cit = M.Citation(
                packet_id=packet_id, packet_item_id=packet_item_id, citation_type=cite_type,
                citation_order=len(citations), anchor_kind=anchor_kind, anchor_id=anchor_id,
                label=f"{cite_type}:{anchor_id}", target_kind=row.get("target_kind"),
                target_id=row.get("target_id"), review_item_id=row.get("review_item_id"),
                projection_item_id=row.get("projection_item_id"), source_digest=row.get("source_digest"),
                card_digest=row.get("card_digest"), target_digest=row.get("target_digest"),
                evidence_excerpt=(entry["evidence"] if budget.include_evidence else None),
                evidence_location=row.get("note_rel_path"), confidence=row.get("confidence"),
                review_state=row.get("review_state"), effective_state=row.get("effective_state"),
                inclusion_state=row.get("inclusion_state"),
                source_id=row.get("source_id"), note_rel_path=row.get("note_rel_path"),
                claim_id=row.get("claim_id"), receipt_id=row.get("receipt_id"), pack_id=row.get("pack_id"),
                pack_item_id=row.get("pack_item_id"), memory_node_id=row.get("memory_node_id"),
                memory_mention_id=row.get("memory_mention_id"), compilation_id=row.get("compilation_id"),
                decision_id=row.get("decision_id"), preference_id=row.get("preference_id"),
                open_loop_id=row.get("open_loop_id"),
            )
            citations.append(cit)
            citation_budget[0] -= 1
    item.citation_ids = [c.citation_id() for c in citations]
    return item, citations


def preview_research_packet(providers: PacketProviders, *, projection_id: str,
                            packet_type: str = M.REVIEW_AWARE_ANSWER_CONTEXT,
                            budget: M.PacketBudget | None = None, title: str | None = None,
                            objective: str | None = None, question: str | None = None,
                            created_by: str = "service", limit: int = 200,
                            conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Build a bounded, citation-backed, review-aware answer-context packet WITHOUT persisting. Read-only."""
    if packet_type not in M.PACKET_TYPES:
        raise M.ResearchPacketValidationError(f"unknown_packet_type:{packet_type}")
    budget = (budget or M.PacketBudget.for_type(packet_type)).clamped()
    header, classified = _classify(providers, projection_id=projection_id, packet_type=packet_type,
                                   budget=budget, limit=limit, conn=conn)
    if header is None:
        raise M.ResearchPacketValidationError(f"projection_not_found:{projection_id}")

    objective = (objective or header.get("objective") or "")[:M.OBJECTIVE_HARD_CAP]
    question = (question or "")[:M.QUESTION_HARD_CAP]
    scope_json = M.canonical_json({"projection_id": projection_id})
    filter_policy_json = M.canonical_json({"packet_type": packet_type})
    budget_json = M.canonical_json(budget.to_dict())

    decorated, counts, truncated = _budget_items(classified, budget=budget)

    # Unresolved questions (bounded) from included open-question items; must_not_say from excluded states.
    unresolved: list[str] = []
    must_entries: list[dict[str, Any]] = []
    for e in decorated:
        row = e["row"]
        if e["included"] and e["answer_role"] == M.ROLE_OPEN_QUESTION and \
                len(unresolved) < budget.max_open_questions:
            q = row.get("title") or row.get("target_id")
            if q:
                unresolved.append(M.bound_text(q, M.MUST_NOT_SAY_ENTRY_CAP))
        if row.get("inclusion_state") in _MUST_NOT_SAY_STATES:
            must_entries.append({"target_kind": row.get("target_kind"), "target_id": row.get("target_id"),
                                 "effective_state": row.get("effective_state"),
                                 "inclusion_state": row.get("inclusion_state"),
                                 "exclusion_reason": e["exclusion_reason"], "label": row.get("title")})
    must_not_say = M.bound_must_not_say(must_entries)

    answer_contract = M.build_answer_contract(packet_type, budget, trusted_included=counts["trusted"],
                                              candidate_included=counts["candidate"],
                                              unresolved_questions=unresolved, must_not_say=must_not_say)
    answer_contract_json = M.canonical_json(answer_contract)
    answer_contract_digest = M.compute_answer_contract_digest(answer_contract)

    signals = [(c["row"].get("projection_item_id") or c["row"].get("target_id") or "",
                c["row"].get("effective_state") or "",
                f"{c['row'].get('target_digest') or ''}#{c['citation_signature']}")
               for c in decorated]
    input_digest = M.compute_packet_input_digest(signals, filter_policy_json, budget_json,
                                                 answer_contract_digest)
    packet_id = M.compute_packet_id(packet_type, projection_id, objective, question,
                                    answer_contract_json, budget_json, input_digest)

    citation_budget = [budget.max_citations]
    item_rows: list[dict[str, Any]] = []
    citation_rows: list[dict[str, Any]] = []
    included_item_ids: list[str] = []
    for e in decorated:
        item, cits = _build_item_and_citations(e, packet_id, projection_id, budget=budget,
                                               citation_budget=citation_budget)
        item_row = item.to_row()
        item_rows.append(item_row)
        if item_row["included"]:
            included_item_ids.append(item_row["packet_item_id"])
        citation_rows.extend(c.to_row() for c in cits)

    output_digest = M.compute_packet_output_digest(included_item_ids)
    citation_count = len(citation_rows)

    packet = {
        "packet_id": packet_id, "packet_type": packet_type,
        "title": (title or f"{packet_type} for projection {projection_id}")[:M.TITLE_HARD_CAP],
        "objective": objective or None, "question": question or None,
        "scope_json": scope_json, "answer_contract_json": answer_contract_json,
        "budget_json": budget_json, "status": "built", "created_by": created_by,
        "projection_id": projection_id, "input_digest": input_digest, "output_digest": output_digest,
        "answer_contract_digest": answer_contract_digest,
        "trusted_count": counts["trusted"], "candidate_count": counts["candidate"],
        "excluded_count": counts["excluded"], "citation_count": citation_count,
        "open_question_count": counts["open_question"], "item_count": len(item_rows),
        "truncated": 1 if truncated else 0,
    }
    receipt = {
        "packet_receipt_id": M.compute_packet_receipt_id(packet_id, input_digest, output_digest,
                                                        answer_contract_digest),
        "packet_id": packet_id, "builder_version": M.RESEARCH_PACKET_BUILDER_VERSION,
        "projection_id": projection_id, "input_digest": input_digest, "output_digest": output_digest,
        "answer_contract_digest": answer_contract_digest, "budget_json": budget_json,
        "trusted_count": counts["trusted"], "candidate_count": counts["candidate"],
        "excluded_count": counts["excluded"], "citation_count": citation_count,
        "open_question_count": counts["open_question"], "dropped_count": counts["dropped"],
        "truncated": 1 if truncated else 0,
    }
    return {"applied": False, "packet_id": packet_id, "packet": packet, "items": item_rows,
            "citations": citation_rows, "receipt": receipt, "answer_contract": answer_contract,
            "counts": counts, "truncated": truncated, "input_digest": input_digest,
            "output_digest": output_digest, "included_count": len(included_item_ids),
            "citation_count": citation_count}


def build_research_packet(providers: PacketProviders, repo: Any, *, projection_id: str,
                          packet_type: str = M.REVIEW_AWARE_ANSWER_CONTEXT,
                          budget: M.PacketBudget | None = None, apply: bool = False,
                          title: str | None = None, objective: str | None = None,
                          question: str | None = None, created_by: str = "service", limit: int = 200,
                          conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Preview, and — only when ``apply`` — persist into the five packet tables (nothing else). Idempotent:
    unchanged inputs create no duplicate; a changed projection/effective-state/citation digest changes
    ``input_digest`` → a new packet that supersedes the prior one of the same type+projection+scope."""
    preview = preview_research_packet(providers, projection_id=projection_id, packet_type=packet_type,
                                      budget=budget, title=title, objective=objective, question=question,
                                      created_by=created_by, limit=limit, conn=conn)
    if not apply:
        return preview
    res = repo.upsert_packet(preview["packet"], preview["items"], preview["citations"],
                             preview["receipt"], conn=conn)
    return {"applied": True, "packet_id": preview["packet_id"], "created": res["created"],
            "reused": res.get("reused", False), "superseded": res.get("superseded", []),
            "counts": preview["counts"], "truncated": preview["truncated"],
            "included_count": preview["included_count"], "citation_count": preview["citation_count"]}


def export_research_packet(repo: Any, *, packet_id: str, included_only: bool = True, limit: int = 200,
                           conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded JSON export of a persisted packet: header + answer contract + bounded items + bounded
    citations. NO raw source/card/vault/email bodies, no full payloads, no answer prose, no writer for
    Markdown/HTML/PDF/doc formats."""
    header = repo.get_research_packet(packet_id, conn=conn)
    if header is None:
        raise M.ResearchPacketValidationError(f"packet_not_found:{packet_id}")
    items = repo.list_research_packet_items(packet_id, included_only=included_only, limit=limit, conn=conn)
    citations = repo.list_research_packet_citations(packet_id, limit=limit, conn=conn)
    answer_contract = None
    if header.get("answer_contract_json"):
        import json
        try:
            answer_contract = json.loads(header["answer_contract_json"])
        except (ValueError, TypeError):
            answer_contract = None
    return {"format": "json", "packet": header, "answer_contract": answer_contract, "items": items,
            "citations": citations, "item_count": len(items), "citation_count": len(citations)}
