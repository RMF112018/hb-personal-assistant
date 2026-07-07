"""N8C-10 review-aware intelligence projection builder — deterministic, source-backed, pack-scoped, NO LLM.

Materializes a bounded, effective-state-filtered projection for ONE context pack by REUSING the N8C-9
review layer (never duplicating it):
  1. ``review_builder.discover_review_candidates`` (read-only) enumerates the pack's review-aware target
     records (claims, context-pack items, enrichment review, memory compilations, decision/preference/
     open-loop records) as anchored, bounded drafts;
  2. ``review_repository.get_effective_state`` (read-only) resolves each draft's effective review state
     (latest disposition, else built default ``candidate``);
  3. ``classify_inclusion_state`` maps effective state → inclusion_state per the projection type's policy;
  4. the budget caps the result (max_items / max_chars / max_chars_per_item / max_trusted / max_candidates).

Reads only — it never mutates a source advisory OR review table, never converts a candidate into accepted
truth, and executes nothing. For ``implementation_context`` open loops are labelled advisory and are NEVER
emitted as executable instructions (the builder only copies bounded descriptive text). ``preview`` is fully
read-only; rows are persisted only by ``build_intelligence_projection(apply=True)`` and only into the four
N8C-10 projection tables (via the repository). Excluded items keep ids/state/digests/exclusion_reason but
carry no unnecessary content.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from . import intelligence_projection_models as M
from . import review_builder as RB
from .context_pack_models import estimate_tokens

# Deterministic inclusion ordering (trusted first).
_INCLUSION_RANK = {
    M.INCL_TRUSTED: 0, M.INCL_CANDIDATE: 1, M.INCL_DEFERRED: 2, M.INCL_STALE: 3,
    M.INCL_NOT_REQUIRED: 4, M.INCL_SUPERSEDED: 5, M.INCL_EXCLUDED: 6,
}
# Effective states that are always excluded regardless of policy → exclusion_reason from the state.
_HARD_EXCLUDE_REASON = {
    M.INCL_EXCLUDED: "rejected", M.INCL_NOT_REQUIRED: "not_required", M.INCL_SUPERSEDED: "superseded",
}


@dataclass
class ProjectionProviders:
    review_providers: Any        # review_builder.ReviewProviders
    review_repo: Any             # review_repository.ReviewRepository


def _classify(providers: ProjectionProviders, *, pack_id: str, kinds: tuple[str, ...],
              budget: M.ProjectionBudget, limit: int,
              conn: sqlite3.Connection | None) -> list[dict[str, Any]]:
    """Read-only: discover review candidates, resolve effective state, classify inclusion. No writes."""
    drafts = RB.discover_review_candidates(providers.review_providers, pack_id=pack_id, kinds=kinds,
                                           limit=limit, conn=conn)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for d in drafts:
        row = d.to_row()
        rid = row["review_item_id"]
        if rid in seen:
            continue
        seen.add(rid)
        eff = providers.review_repo.get_effective_state(rid, conn=conn)
        effective_state = eff["effective_state"] if eff else "candidate"
        review_state = eff["effective_review_state"] if eff else row.get("review_state")
        disposition_id = eff.get("latest_disposition_id") if eff else None
        inclusion_state, policy_included = M.classify_inclusion_state(effective_state, budget)
        out.append({
            "row": row, "review_item_id": rid, "effective_state": effective_state,
            "review_state": review_state, "disposition_id": disposition_id,
            "inclusion_state": inclusion_state, "policy_included": policy_included,
        })
    # Deterministic order: inclusion rank, then confidence desc, then target for stable ties.
    out.sort(key=lambda x: (_INCLUSION_RANK.get(x["inclusion_state"], 9),
                            -(x["row"].get("confidence") or 0.0),
                            x["row"].get("target_kind") or "", x["row"].get("target_id") or ""))
    return out


def _policy_exclusion_reason(inclusion_state: str) -> str:
    return _HARD_EXCLUDE_REASON.get(inclusion_state, f"policy_{inclusion_state}")


def _build_items(classified: list[dict[str, Any]], *, projection_type: str,
                 budget: M.ProjectionBudget) -> tuple[list[M.ProjectionItem], dict[str, int], bool]:
    """Apply the budget over the ordered classified items → ProjectionItem drafts + counts + truncated."""
    items: list[M.ProjectionItem] = []
    counts = {"trusted": 0, "candidate": 0, "excluded": 0, "stale": 0, "superseded": 0,
              "not_required": 0, "deferred": 0, "dropped": 0}
    running_chars = 0
    trusted_used = candidate_used = items_used = 0
    truncated = False
    is_impl = projection_type == M.IMPLEMENTATION_CONTEXT

    for order, c in enumerate(classified):
        row = c["row"]
        inc = c["inclusion_state"]
        included = False
        reason: str | None = None
        title = row.get("title")
        summary = row.get("summary")
        evidence = row.get("evidence_excerpt") if budget.include_evidence else None
        token_est = 0

        if not c["policy_included"]:
            reason = _policy_exclusion_reason(inc)
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
                token_est = estimate_tokens(f"{title or ''} {summary or ''}") + estimate_tokens(evidence)

        # Excluded items keep ids/state/digests/exclusion_reason but carry no unnecessary content.
        if not included:
            summary = None
            evidence = None
            if reason and reason.startswith("budget_"):
                counts["dropped"] += 1
        counts[inc] = counts.get(inc, 0) + 1

        meta: dict[str, Any] = {}
        if is_impl and row.get("target_kind") == "open_loop":
            meta["advisory"] = True  # open loops are advisory only — never executable instructions
        if c["review_item_id"]:
            meta["review_item_id"] = c["review_item_id"]

        items.append(M.ProjectionItem(
            target_kind=row.get("target_kind"), target_id=row.get("target_id"),
            inclusion_state=inc, included=included, item_order=order,
            review_item_id=c["review_item_id"], disposition_id=c["disposition_id"],
            effective_state=c["effective_state"], review_state=c["review_state"],
            title=title, summary=summary, evidence_excerpt=evidence,
            confidence=row.get("confidence"), priority=row.get("priority"),
            token_estimate=token_est, exclusion_reason=reason,
            source_id=row.get("source_id"), note_rel_path=row.get("note_rel_path"),
            claim_id=row.get("claim_id"), receipt_id=row.get("receipt_id"), pack_id=row.get("pack_id"),
            pack_item_id=row.get("pack_item_id"), memory_node_id=row.get("memory_node_id"),
            memory_mention_id=row.get("memory_mention_id"), compilation_id=row.get("compilation_id"),
            decision_id=row.get("decision_id"), preference_id=row.get("preference_id"),
            open_loop_id=row.get("open_loop_id"), source_digest=row.get("source_digest"),
            card_digest=row.get("card_digest"), target_digest=row.get("target_digest"),
            metadata=meta,
        ))
    return items, counts, truncated


def preview_intelligence_projection(providers: ProjectionProviders, *, pack_id: str,
                                    projection_type: str = M.REVIEW_AWARE_CONTEXT,
                                    budget: M.ProjectionBudget | None = None,
                                    kinds: tuple[str, ...] = RB.ALL_KINDS, title: str | None = None,
                                    objective: str | None = None, created_by: str = "service",
                                    limit: int = 200,
                                    conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Build a bounded, review-aware projection for a pack WITHOUT persisting. Fully read-only."""
    if projection_type not in M.PROJECTION_TYPES:
        raise M.ProjectionValidationError(f"unknown_projection_type:{projection_type}")
    budget = (budget or M.ProjectionBudget.for_type(projection_type)).clamped()
    scope_json = M.canonical_json({"pack_id": pack_id, "kinds": list(kinds)})
    filter_policy_json = M.canonical_json({"projection_type": projection_type})
    budget_json = M.canonical_json(budget.to_dict())

    classified = _classify(providers, pack_id=pack_id, kinds=kinds, budget=budget, limit=limit, conn=conn)
    signals = [(c["review_item_id"], c["effective_state"], c["row"].get("target_digest") or "")
               for c in classified]
    input_digest = M.compute_input_digest(signals, filter_policy_json, budget_json)
    projection_id = M.compute_projection_id(projection_type, scope_json, filter_policy_json, budget_json,
                                            input_digest)

    drafts, counts, truncated = _build_items(classified, projection_type=projection_type, budget=budget)
    item_rows = [d.to_row(projection_id) for d in drafts]
    included_ids = [r["projection_item_id"] for r in item_rows if r["included"]]
    output_digest = M.compute_output_digest(included_ids)

    header = {
        "projection_id": projection_id, "projection_type": projection_type,
        "title": (title or f"{projection_type} for pack {pack_id}")[:M.TITLE_HARD_CAP],
        "objective": (objective or "")[:M.OBJECTIVE_HARD_CAP] or None,
        "scope_json": scope_json, "filter_policy_json": filter_policy_json, "budget_json": budget_json,
        "status": "built", "input_digest": input_digest, "output_digest": output_digest,
        "trusted_count": counts.get("trusted", 0), "candidate_count": counts.get("candidate", 0),
        "excluded_count": counts.get("excluded", 0), "stale_count": counts.get("stale", 0),
        "superseded_count": counts.get("superseded", 0), "item_count": len(item_rows),
        "truncated": 1 if truncated else 0, "created_by": created_by,
    }
    receipt = {
        "projection_receipt_id": M.compute_projection_receipt_id(projection_id, input_digest,
                                                                 output_digest),
        "projection_id": projection_id, "builder_version": M.PROJECTION_BUILDER_VERSION,
        "input_digest": input_digest, "output_digest": output_digest,
        "filter_policy_json": filter_policy_json, "budget_json": budget_json,
        "trusted_count": counts.get("trusted", 0), "candidate_count": counts.get("candidate", 0),
        "excluded_count": counts.get("excluded", 0), "stale_count": counts.get("stale", 0),
        "superseded_count": counts.get("superseded", 0), "dropped_count": counts.get("dropped", 0),
        "truncated": 1 if truncated else 0,
    }
    return {"applied": False, "projection_id": projection_id, "projection": header,
            "items": item_rows, "receipt": receipt, "counts": counts, "truncated": truncated,
            "input_digest": input_digest, "output_digest": output_digest,
            "included_count": len(included_ids)}


def build_intelligence_projection(providers: ProjectionProviders, repo: Any, *, pack_id: str,
                                  projection_type: str = M.REVIEW_AWARE_CONTEXT,
                                  budget: M.ProjectionBudget | None = None,
                                  kinds: tuple[str, ...] = RB.ALL_KINDS, apply: bool = False,
                                  title: str | None = None, objective: str | None = None,
                                  created_by: str = "service", limit: int = 200,
                                  conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Preview, and — only when ``apply`` — persist into the four projection tables (nothing else).
    Idempotent: unchanged inputs create no duplicate; a changed effective state (new disposition) changes
    ``input_digest`` → a new projection that supersedes the prior one of the same type+scope."""
    preview = preview_intelligence_projection(
        providers, pack_id=pack_id, projection_type=projection_type, budget=budget, kinds=kinds,
        title=title, objective=objective, created_by=created_by, limit=limit, conn=conn)
    if not apply:
        return preview
    res = repo.upsert_projection(preview["projection"], preview["items"], preview["receipt"], conn=conn)
    return {"applied": True, "projection_id": preview["projection_id"], "created": res["created"],
            "reused": res.get("reused", False), "superseded": res.get("superseded", []),
            "counts": preview["counts"], "truncated": preview["truncated"],
            "included_count": preview["included_count"]}


def export_intelligence_projection(repo: Any, *, projection_id: str, included_only: bool = True,
                                   limit: int = 200,
                                   conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded JSON export of a persisted projection: header + bounded items (ids/digests/state + bounded
    excerpts). No raw source/card/vault bodies, no full payloads, no raw prompts/responses."""
    header = repo.get_projection(projection_id, conn=conn)
    if header is None:
        raise M.ProjectionValidationError(f"projection_not_found:{projection_id}")
    items = repo.list_projection_items(projection_id, included_only=included_only, limit=limit, conn=conn)
    return {"format": "json", "projection": header, "items": items, "count": len(items)}
