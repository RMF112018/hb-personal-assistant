"""N8C-9 review-queue builder — deterministic, source-backed, pack-scoped, NO LLM.

Discovers review candidates for ONE context pack from the existing advisory records (claims, context-pack
items, enrichment review, memory compilations, decision/preference/open-loop records) and turns each into
a bounded ``ReviewItem`` draft anchored to the target record + its source evidence. Reads only — it never
mutates a source table.

Scope discipline: the build is ALWAYS pack-scoped (``pack_id`` is required). ``kinds`` narrows which
families are included WITHIN that pack; there is no global "review everything" mode (deferred). Every
family read is bounded.

``preview_review_queue`` is fully read-only. Rows are persisted only by ``build_review_queue(..., apply=
True)`` and only into ``assistant_review_items`` (via the repository). Building a review item NEVER accepts
the underlying record — candidate claims/decisions stay candidate/unreviewed.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from . import review_models as RM
from .memory_models import bound_text, sha256_hex

# Family selectors for ``--kind``. Default = all.
KIND_CLAIMS = "claims"
KIND_CONTEXT_PACKS = "context-packs"
KIND_ENRICHMENT = "enrichment"
KIND_MEMORY = "memory"
KIND_DECISIONS = "decisions"
KIND_PREFERENCES = "preferences"
KIND_OPEN_LOOPS = "open-loops"
ALL_KINDS = (KIND_CLAIMS, KIND_CONTEXT_PACKS, KIND_ENRICHMENT, KIND_MEMORY, KIND_DECISIONS,
             KIND_PREFERENCES, KIND_OPEN_LOOPS)

_SAFE_SUMMARY = "safe_summary"
_LOW_CONFIDENCE = 0.4
_STALE_SOURCE_STATES = frozenset({"stale", "missing", "moved", "deleted"})


@dataclass
class ReviewProviders:
    pack_repo: Any
    claim_repo: Any
    enrichment_repo: Any
    source_repo: Any
    memory_repo: Any
    decision_memory_repo: Any


def _digest(*parts: Any) -> str:
    return sha256_hex("|".join("" if p is None else str(p) for p in parts))[:24]


def _is_stale_source(source_state: Any) -> bool:
    return bool(source_state) and str(source_state) in _STALE_SOURCE_STATES


# --- per-family classification (each returns a ReviewItem draft or None) -----------------
def _claim_review(claim: dict[str, Any], pack_id: str, pack_item_id: str | None) -> RM.ReviewItem | None:
    status = claim.get("status")
    review_state = claim.get("review_state")
    claim_type = claim.get("claim_type")
    conf = claim.get("confidence")
    source_state = claim.get("source_state")
    # A claim is a review candidate when it is still candidate/unreviewed, is a decision/task/contradiction
    # candidate, is low-confidence, or its source drifted. Otherwise it needs no review.
    interesting = (
        status == "candidate" or review_state in ("unreviewed", "needs_review")
        or claim_type in ("decision_candidate", "task_candidate", "commitment", "risk",
                          "contradiction_candidate")
        or (conf is not None and conf < _LOW_CONFIDENCE)
        or _is_stale_source(source_state)
    )
    if not interesting:
        return None
    stale = _is_stale_source(source_state)
    state_digest = _digest(status, review_state, conf, source_state)
    content_digest = _digest("claim", claim.get("claim_id"), claim.get("card_id"),
                             claim.get("claim_text"))
    review_state_out = RM.REVIEW_NEEDS_REVIEW if (stale or (conf is not None and conf < _LOW_CONFIDENCE)) \
        else RM.REVIEW_UNREVIEWED
    return RM.ReviewItem(
        target_kind="claim", target_id=str(claim.get("claim_id")),
        target_digest=_digest(content_digest, state_digest), target_state_digest=state_digest,
        review_type="claim_review",
        title=bound_text(claim.get("normalized_subject") or claim.get("claim_type"), RM.TITLE_HARD_CAP),
        summary=bound_text(claim.get("claim_text"), RM.SUMMARY_HARD_CAP),
        review_state=review_state_out, confidence=conf, stale=stale,
        source_id=claim.get("source_id"), note_rel_path=claim.get("note_rel_path"),
        claim_id=claim.get("claim_id"), pack_id=pack_id, pack_item_id=pack_item_id,
        evidence_excerpt=claim.get("evidence_excerpt"), evidence_location=claim.get("evidence_location"),
        card_digest=claim.get("card_id"),
        metadata={"claim_type": claim_type, "claim_status": status},
    )


def _context_pack_item_review(item: dict[str, Any], pack_id: str) -> RM.ReviewItem | None:
    tier = item.get("review_tier")
    if not tier or tier == _SAFE_SUMMARY:
        return None
    conf = item.get("confidence")
    source_state = item.get("source_state")
    stale = _is_stale_source(source_state)
    state_digest = _digest(tier, conf, source_state)
    content_digest = _digest("context_pack_item", item.get("pack_item_id"), item.get("item_type"),
                             item.get("result_digest") or item.get("card_digest"))
    return RM.ReviewItem(
        target_kind="context_pack_item", target_id=str(item.get("pack_item_id")),
        target_digest=_digest(content_digest, state_digest), target_state_digest=state_digest,
        review_type="context_pack_review",
        title=bound_text(f"{item.get('item_type')} ({tier})", RM.TITLE_HARD_CAP),
        summary=bound_text(item.get("note_rel_path") or item.get("item_type"), RM.SUMMARY_HARD_CAP),
        review_state=RM.REVIEW_NEEDS_REVIEW, confidence=conf, priority=tier, stale=stale,
        source_id=item.get("source_id"), note_rel_path=item.get("note_rel_path"),
        claim_id=item.get("claim_id"), pack_id=pack_id, pack_item_id=item.get("pack_item_id"),
        card_digest=item.get("card_digest"), source_digest=item.get("result_digest"),
        metadata={"item_type": item.get("item_type"), "review_tier": tier},
    )


def _enrichment_review(it: dict[str, Any], pack_id: str) -> RM.ReviewItem | None:
    tier = it.get("review_tier")
    if not tier or tier == _SAFE_SUMMARY:
        return None
    conf = it.get("confidence")
    source_state = it.get("source_state")
    stale = _is_stale_source(source_state) or tier == "source_stale"
    state_digest = _digest(tier, conf, source_state, it.get("review_state"))
    content_digest = _digest("enrichment_review_item", it.get("review_item_id"),
                             it.get("result_digest"))
    return RM.ReviewItem(
        target_kind="enrichment_review_item", target_id=str(it.get("review_item_id")),
        target_digest=_digest(content_digest, state_digest), target_state_digest=state_digest,
        review_type="enrichment_review",
        title=bound_text(f"{it.get('review_item_type')} ({tier})", RM.TITLE_HARD_CAP),
        summary=bound_text(it.get("summary"), RM.SUMMARY_HARD_CAP),
        review_state=RM.REVIEW_NEEDS_REVIEW, confidence=conf, priority=tier, stale=stale,
        source_id=it.get("source_id"), note_rel_path=it.get("note_rel_path"),
        claim_id=it.get("claim_id"), receipt_id=it.get("receipt_id"), pack_id=pack_id,
        evidence_excerpt=it.get("evidence_excerpt"), source_digest=it.get("result_digest"),
        metadata={"review_item_type": it.get("review_item_type"), "review_tier": tier},
    )


def _memory_compilation_review(comp: dict[str, Any], pack_id: str,
                               rep: dict[str, Any]) -> RM.ReviewItem | None:
    tier = comp.get("review_tier")
    stale_count = comp.get("stale_count") or 0
    truncated = comp.get("truncated") or 0
    # Include when the compilation needs operator review, is stale, or was truncated.
    interesting = (tier and tier != _SAFE_SUMMARY) or int(stale_count) > 0 or int(truncated) > 0
    if not interesting:
        return None
    stale = int(stale_count) > 0
    state_digest = _digest(tier, stale_count, truncated, comp.get("status"))
    content_digest = _digest("memory_compilation", comp.get("compilation_id"),
                             comp.get("output_digest"))
    return RM.ReviewItem(
        target_kind="memory_compilation", target_id=str(comp.get("compilation_id")),
        target_digest=_digest(content_digest, state_digest), target_state_digest=state_digest,
        review_type="memory_review",
        title=bound_text(f"compilation {comp.get('compile_type')}", RM.TITLE_HARD_CAP),
        summary=bound_text(comp.get("summary"), RM.SUMMARY_HARD_CAP),
        review_state=RM.REVIEW_NEEDS_REVIEW, priority=tier, stale=stale,
        compilation_id=comp.get("compilation_id"), memory_node_id=comp.get("node_id"),
        source_id=rep.get("source_id"), note_rel_path=rep.get("note_rel_path"),
        source_digest=comp.get("output_digest"),
        metadata={"compile_type": comp.get("compile_type"), "review_tier": tier,
                  "stale_count": int(stale_count), "truncated": int(truncated)},
    )


def _decision_family_review(record: dict[str, Any], *, kind: str, pk: str, review_type: str,
                            target_kind: str, subject_key: str,
                            text_key: str) -> RM.ReviewItem | None:
    if record.get("status") != "candidate" or record.get("review_state") not in (
            "unreviewed", "needs_review"):
        return None
    conf = record.get("confidence")
    state_digest = _digest(record.get("status"), record.get("review_state"), conf)
    content_digest = _digest(target_kind, record.get(pk), record.get("source_digest"),
                             record.get("evidence_excerpt"))
    anchors: dict[str, Any] = {
        "source_id": record.get("source_id"), "note_rel_path": record.get("note_rel_path"),
        "claim_id": record.get("claim_id"), "pack_id": record.get("pack_id"),
        "pack_item_id": record.get("pack_item_id"), "memory_node_id": record.get("memory_node_id"),
        "compilation_id": record.get("compilation_id"),
    }
    anchors[pk] = record.get(pk)  # decision_id / preference_id / open_loop_id
    review_state_out = record.get("review_state") if record.get("review_state") in (
        "unreviewed", "needs_review") else RM.REVIEW_UNREVIEWED
    return RM.ReviewItem(
        target_kind=target_kind, target_id=str(record.get(pk)),
        target_digest=_digest(content_digest, state_digest), target_state_digest=state_digest,
        review_type=review_type,
        title=bound_text(record.get(subject_key) or target_kind, RM.TITLE_HARD_CAP),
        summary=bound_text(record.get(text_key), RM.SUMMARY_HARD_CAP),
        review_state=review_state_out, confidence=conf,
        evidence_excerpt=record.get("evidence_excerpt"),
        evidence_location=record.get("evidence_location"),
        source_digest=record.get("source_digest"), card_digest=record.get("card_digest"),
        metadata={f"{target_kind}_type": record.get(f"{target_kind}_type")},
        **anchors,
    )


# --- discovery --------------------------------------------------------------------------
def discover_review_candidates(providers: ReviewProviders, *, pack_id: str,
                               kinds: tuple[str, ...] = ALL_KINDS, limit: int = 200,
                               conn: sqlite3.Connection | None = None) -> list[RM.ReviewItem]:
    """Pack-scoped, read-only discovery across the selected advisory families."""
    drafts: list[RM.ReviewItem] = []
    items = providers.pack_repo.list_items(pack_id, conn=conn)
    source_ids: list[str] = []
    for item in items:
        if item.get("source_id"):
            source_ids.append(item["source_id"])
        if not item.get("included", 1):
            continue
        if KIND_CONTEXT_PACKS in kinds:
            rec = _context_pack_item_review(item, pack_id)
            if rec is not None:
                drafts.append(rec)
        if KIND_CLAIMS in kinds and item.get("item_type") == "claim_candidate" and item.get("claim_id"):
            claim = providers.claim_repo.get_claim(item["claim_id"], conn=conn)
            if claim is not None:
                rec = _claim_review(claim, pack_id, item.get("pack_item_id"))
                if rec is not None:
                    drafts.append(rec)

    pack_source_ids = frozenset(s for s in source_ids if s)

    if KIND_ENRICHMENT in kinds:
        from . import enrichment_review as ER
        env = ER.list_enrichment_review_items(
            providers.enrichment_repo, providers.claim_repo, providers.source_repo,
            limit=limit, conn=conn)
        for it in env.get("review_items", []):
            if pack_source_ids and it.get("source_id") not in pack_source_ids:
                continue
            rec = _enrichment_review(it, pack_id)
            if rec is not None:
                drafts.append(rec)

    if KIND_MEMORY in kinds:
        for comp in providers.memory_repo.list_built_compilations_for_sources(
                list(pack_source_ids), conn=conn):
            mentions = providers.memory_repo.list_mentions(comp["node_id"], limit=1, conn=conn)
            rep = mentions[0] if mentions else {}
            rec = _memory_compilation_review(comp, pack_id, rep)
            if rec is not None:
                drafts.append(rec)

    dm = providers.decision_memory_repo
    if KIND_DECISIONS in kinds:
        for r in dm.list_decisions(status="candidate", limit=limit, conn=conn):
            if r.get("pack_id") == pack_id:
                rec = _decision_family_review(r, kind="decision", pk="decision_id",
                                              review_type="decision_review", target_kind="decision",
                                              subject_key="normalized_subject", text_key="decision_text")
                if rec is not None:
                    drafts.append(rec)
    if KIND_PREFERENCES in kinds:
        for r in dm.list_preferences(status="candidate", limit=limit, conn=conn):
            if r.get("pack_id") == pack_id:
                rec = _decision_family_review(r, kind="preference", pk="preference_id",
                                              review_type="preference_review", target_kind="preference",
                                              subject_key="normalized_subject",
                                              text_key="preference_text")
                if rec is not None:
                    drafts.append(rec)
    if KIND_OPEN_LOOPS in kinds:
        for r in dm.list_open_loops(status="candidate", limit=limit, conn=conn):
            if r.get("pack_id") == pack_id:
                rec = _decision_family_review(r, kind="open_loop", pk="open_loop_id",
                                              review_type="open_loop_review", target_kind="open_loop",
                                              subject_key="normalized_subject",
                                              text_key="open_loop_text")
                if rec is not None:
                    drafts.append(rec)
    return drafts


def _to_rows(drafts: list[RM.ReviewItem], created_by: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for d in drafts:
        row = {**d.to_row(), "created_by": created_by}
        rid = row["review_item_id"]
        if rid in seen:  # deterministic dedup — same target+digest+review_type collapses to one item
            continue
        seen.add(rid)
        rows.append(row)
    return rows


def preview_review_queue(providers: ReviewProviders, *, pack_id: str, kinds: tuple[str, ...] = ALL_KINDS,
                         created_by: str = "service", limit: int = 200,
                         conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Discover + build review rows for a pack WITHOUT persisting. Fully read-only."""
    drafts = discover_review_candidates(providers, pack_id=pack_id, kinds=kinds, limit=limit, conn=conn)
    rows = _to_rows(drafts, created_by)
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["review_type"]] = by_type.get(r["review_type"], 0) + 1
    return {"pack_id": pack_id, "kinds": list(kinds), "items": rows, "count": len(rows),
            "by_review_type": by_type}


def build_review_queue(providers: ReviewProviders, repo: Any, *, pack_id: str,
                       kinds: tuple[str, ...] = ALL_KINDS, apply: bool = False,
                       created_by: str = "service", limit: int = 200,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Discover + build, and — only when ``apply`` — persist into ``assistant_review_items`` (nothing
    else). Idempotent: unchanged inputs create no duplicates; a changed target digest supersedes the
    prior item of the same target lineage."""
    preview = preview_review_queue(providers, pack_id=pack_id, kinds=kinds, created_by=created_by,
                                   limit=limit, conn=conn)
    if not apply:
        return {"applied": False, **preview}
    created = 0
    superseded = 0
    for row in preview["items"]:
        res = repo.upsert_review_item(row, conn=conn)
        created += 1 if res["created"] else 0
        superseded += len(res.get("superseded", []))
    return {"applied": True, "pack_id": pack_id, "kinds": list(kinds), "created": created,
            "superseded": superseded, "count": preview["count"],
            "by_review_type": preview["by_review_type"]}
