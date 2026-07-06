"""N8C-6 context-pack builder — assembles bounded, source-linked intelligence packets.

Turns the N8C substrate (enrichment receipts, candidate claims, sources/cards) into a reproducible,
digest/stale-aware pack. Preview and dry-run are fully read-only; a pack is persisted only via
``build_context_pack(..., apply=True)`` and only into the four context-pack-owned tables.

Boundaries baked in:
  * SQLite stays the source of truth; enrichment output is advisory. Nothing here accepts a claim or
    flips a claim ``review_state`` (candidate claims stay candidate/unreviewed).
  * Items carry only BOUNDED selected excerpts — never a full enrichment ``result_json`` (linked by
    ``receipt_id`` + ``result_digest`` instead) and never raw prompts/responses or raw email bodies.
  * Unsafe source state is labeled, never silently trusted: ambiguous card link → needs_operator_review,
    deleted/missing/stale source → source_stale. Mirrors the N8C-4 ``extract_claims_for_card`` order.
  * No automatic stale scan: a pack goes stale only via an explicit ``mark_context_pack_stale_if_needed``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from . import enrichment_review as review
from .context_pack_models import (
    BUILDER_VERSION,
    CONTENT_DEEP_BOUNDED,
    CONTENT_METADATA_ONLY,
    ITEM_CLAIM_CANDIDATE,
    ITEM_SOURCE,
    ITEM_SOURCE_SUMMARY,
    PACK_ENRICHMENT_REVIEW,
    PACK_IMPLEMENTATION_CONTEXT,
    PACK_SOURCE_REVIEW,
    TIER_CLAIM_CANDIDATE,
    TIER_NEEDS_OPERATOR_REVIEW,
    TIER_SAFE_SUMMARY,
    TIER_SOURCE_STALE,
    Budget,
    ContextPackValidationError,
    PackItem,
    bound_text,
    clamp_confidence,
    compute_pack_id,
    estimate_tokens,
    normalize_budget,
    normalize_scope,
    sha256_hex,
    validate_pack_type,
)

# Deterministic ordering: integrity problems surface first, then trusted-summary, then the rest.
_TIER_RANK = {
    TIER_NEEDS_OPERATOR_REVIEW: 0,
    TIER_SOURCE_STALE: 1,
    "conflict_or_contradiction": 2,
    "low_confidence": 3,
    TIER_CLAIM_CANDIDATE: 4,
    "link_candidate": 5,
    TIER_SAFE_SUMMARY: 6,
}
_EXCERPT_LEVEL_CAP = 500  # "excerpt" content level per-item ceiling (deep_bounded uses the full budget)


@dataclass
class PackRequest:
    pack_type: str
    scope: dict[str, Any] = field(default_factory=dict)
    budget: Budget = field(default_factory=Budget)
    title: str | None = None
    objective: str | None = None
    created_by: str = "service"

    def normalized(self) -> PackRequest:
        return PackRequest(
            pack_type=validate_pack_type(self.pack_type),
            scope=dict(self.scope or {}),
            budget=self.budget.normalized(),
            title=self.title,
            objective=self.objective,
            created_by=self.created_by or "service",
        )


@dataclass
class Providers:
    enrichment_repo: Any
    claim_repo: Any
    source_repo: Any


# --- gather (read-only) -----------------------------------------------------------------
def _gather(request: PackRequest, providers: Providers, *,
            conn: sqlite3.Connection | None) -> list[PackItem]:
    scope = request.scope
    budget = request.budget
    if request.pack_type == PACK_ENRICHMENT_REVIEW:
        return _gather_enrichment_review(scope, budget, providers, conn=conn)
    if request.pack_type in (PACK_SOURCE_REVIEW, PACK_IMPLEMENTATION_CONTEXT):
        return _gather_source_centric(request.pack_type, scope, budget, providers, conn=conn)
    raise ContextPackValidationError(f"unsupported_pack_type:{request.pack_type}")


def _gather_enrichment_review(scope: dict[str, Any], budget: Budget, providers: Providers, *,
                              conn: sqlite3.Connection | None) -> list[PackItem]:
    env = review.list_enrichment_review_items(
        providers.enrichment_repo, providers.claim_repo, providers.source_repo,
        limit=min(200, budget.max_items * 2 + 8), job_type=scope.get("job_type"),
        review_tier=scope.get("review_tier"), conn=conn,
    )
    want_sources = set(scope.get("source_ids") or [])
    items: list[PackItem] = []
    for ri in env["review_items"]:
        if want_sources and ri.get("source_id") not in want_sources:
            continue
        items.append(PackItem(
            item_type=_review_type_to_item(ri["review_item_type"]),
            source_id=ri.get("source_id"), note_rel_path=ri.get("note_rel_path"),
            claim_id=ri.get("claim_id"), job_id=ri.get("job_id"), receipt_id=ri.get("receipt_id"),
            title=bound_text(ri.get("summary"), 120) if ri.get("summary") else ri["review_item_type"],
            content_excerpt=ri.get("summary"), evidence_excerpt=ri.get("evidence_excerpt"),
            result_digest=ri.get("result_digest"), source_state=ri.get("source_state"),
            confidence=ri.get("confidence"), review_tier=ri.get("review_tier"),
            metadata={"review_item_id": ri["review_item_id"], "review_state": ri.get("review_state")},
        ))
    return items


def _gather_source_centric(pack_type: str, scope: dict[str, Any], budget: Budget,
                           providers: Providers, *,
                           conn: sqlite3.Connection | None) -> list[PackItem]:
    source_ids = list(scope.get("source_ids") or [])[: budget.max_sources]
    items: list[PackItem] = []
    for sid in source_ids:
        detail = providers.source_repo.get_source_detail(sid, conn=conn)
        src_state = review._source_state(providers.source_repo, sid, conn=conn)
        note_rel_path = detail.get("rel_path") if detail else None
        resolution = review._resolution(providers.source_repo, note_rel_path, conn=conn)
        # A 'source' context item (bounded indexed excerpt only — never raw body).
        excerpt = detail.get("text_excerpt") if detail else None
        tier = _integrity_tier(src_state, resolution)
        items.append(PackItem(
            item_type=ITEM_SOURCE, source_id=sid, note_rel_path=note_rel_path,
            title=bound_text(detail.get("rel_path"), 120) if detail else sid,
            content_excerpt=excerpt, source_digest=detail.get("content_sha256") if detail else None,
            source_state=src_state, review_tier=tier,
        ))
        # Candidate claims for the source (read-only; they stay candidate/unreviewed).
        for cl in providers.claim_repo.get_claims_for_source(sid, limit=budget.max_claims, conn=conn):
            if cl.get("status") != "candidate":
                continue
            items.append(PackItem(
                item_type=ITEM_CLAIM_CANDIDATE, source_id=cl.get("source_id"),
                note_rel_path=cl.get("note_rel_path"), claim_id=cl.get("claim_id"),
                title=bound_text(cl.get("claim_text"), 120), content_excerpt=None,
                evidence_excerpt=cl.get("evidence_excerpt"),
                source_state=cl.get("source_state") or src_state,
                confidence=clamp_confidence(cl.get("confidence")), review_tier=TIER_CLAIM_CANDIDATE,
                metadata={"review_state": cl.get("review_state")},
            ))
        # implementation_context additionally folds in the source_summary review item (safe context).
        if pack_type == PACK_IMPLEMENTATION_CONTEXT:
            env = review.list_enrichment_review_items(
                providers.enrichment_repo, providers.claim_repo, providers.source_repo,
                limit=8, job_type="source_summary", conn=conn,
            )
            for ri in env["review_items"]:
                if ri.get("source_id") != sid:
                    continue
                items.append(PackItem(
                    item_type=ITEM_SOURCE_SUMMARY, source_id=sid,
                    note_rel_path=ri.get("note_rel_path"), receipt_id=ri.get("receipt_id"),
                    job_id=ri.get("job_id"), title="source summary",
                    content_excerpt=ri.get("summary"), result_digest=ri.get("result_digest"),
                    source_state=ri.get("source_state"), confidence=ri.get("confidence"),
                    review_tier=ri.get("review_tier"),
                ))
    return items


def _review_type_to_item(review_item_type: str) -> str:
    from .context_pack_models import ITEM_BACKLINK_SUGGESTION, ITEM_UNKNOWN
    return {
        "source_summary": ITEM_SOURCE_SUMMARY,
        "claim_candidate": ITEM_CLAIM_CANDIDATE,
        "backlink_suggestion": ITEM_BACKLINK_SUGGESTION,
    }.get(review_item_type, ITEM_UNKNOWN)


def _integrity_tier(source_state: str, resolution: str) -> str:
    if resolution == "ambiguous":
        return TIER_NEEDS_OPERATOR_REVIEW
    if source_state in (review.SRC_DELETED, review.SRC_MISSING, review.SRC_STALE):
        return TIER_SOURCE_STALE
    return TIER_SAFE_SUMMARY


# --- budget (deterministic) -------------------------------------------------------------
def _sort_key(pi: PackItem) -> tuple[Any, ...]:
    return (
        _TIER_RANK.get(pi.review_tier or "", 9),
        -(pi.confidence if pi.confidence is not None else 0.0),
        pi.source_id or "",
        pi.item_type,
        pi.claim_id or pi.receipt_id or pi.note_rel_path or "",
    )


def _per_item_cap(budget: Budget) -> int:
    if budget.include_content_level == CONTENT_METADATA_ONLY:
        return 0
    if budget.include_content_level == CONTENT_DEEP_BOUNDED:
        return budget.max_chars_per_item
    return min(budget.max_chars_per_item, _EXCERPT_LEVEL_CAP)  # "excerpt"


def _apply_budget(items: list[PackItem], budget: Budget) -> tuple[list[PackItem], dict[str, Any]]:
    """Order deterministically, then cap by max_items / per-item chars / total chars.

    Every item is retained as a row; over-budget ones are marked ``included=False`` with an
    ``exclusion_reason`` (nothing is silently dropped). Returns (ordered_items, accounting).
    """
    ordered = sorted(items, key=_sort_key)
    per_cap = _per_item_cap(budget)
    running = 0
    included = 0
    truncated = False
    for order, pi in enumerate(ordered):
        pi.item_order = order
        if included >= budget.max_items:
            _exclude(pi, "budget_max_items")
            truncated = True
            continue
        # Bound the item's own content to the per-item cap (0 => metadata_only: drop the excerpt).
        content = bound_text(pi.content_excerpt, per_cap) if (pi.content_excerpt and per_cap > 0) else None
        remaining = budget.max_chars - running
        if remaining <= 0:
            _exclude(pi, "budget_max_chars")
            truncated = True
            continue
        if content and len(content) > remaining:
            content = bound_text(content, remaining)
            truncated = True
        pi.content_excerpt = content
        pi.token_estimate = estimate_tokens(content) + estimate_tokens(pi.evidence_excerpt)
        running += len(content or "")
        included += 1
    stale = sum(1 for pi in ordered if pi.included and pi.review_tier in (TIER_SOURCE_STALE,
                TIER_NEEDS_OPERATOR_REVIEW))
    accounting = {
        "included_count": included,
        "excluded_count": len(ordered) - included,
        "truncated": truncated,
        "total_chars": running,
        "total_token_estimate": sum(pi.token_estimate for pi in ordered if pi.included),
        "stale_count": stale,
    }
    return ordered, accounting


def _exclude(pi: PackItem, reason: str) -> None:
    pi.included = False
    pi.exclusion_reason = reason
    pi.content_excerpt = None
    pi.evidence_excerpt = None
    pi.token_estimate = 0


# --- digests ----------------------------------------------------------------------------
def _input_digest(items: list[PackItem], scope_json: str, budget_json: str) -> str:
    """Digest of the INPUT state so a changed source/receipt yields a new pack_id + stale detection."""
    anchors = sorted(
        f"{pi.item_type}|{pi.source_id or ''}|{pi.claim_id or ''}|{pi.receipt_id or ''}|"
        f"{pi.source_digest or ''}|{pi.result_digest or ''}|{pi.source_state or ''}"
        for pi in items
    )
    return sha256_hex(json.dumps({"scope": scope_json, "budget": budget_json, "anchors": anchors},
                                 sort_keys=True))


def _output_digest(rows: list[dict[str, Any]]) -> str:
    canonical = [
        {k: r.get(k) for k in ("item_order", "item_type", "source_id", "claim_id", "receipt_id",
                               "content_excerpt", "evidence_excerpt", "review_tier", "included",
                               "exclusion_reason")}
        for r in rows
    ]
    return sha256_hex(json.dumps(canonical, sort_keys=True))


# --- assemble / preview / build ---------------------------------------------------------
def _assemble(request: PackRequest, providers: Providers, *,
              conn: sqlite3.Connection | None) -> dict[str, Any]:
    req = request.normalized()
    scope_json = normalize_scope(req.scope)
    budget_json = normalize_budget(req.budget)
    gathered = _gather(req, providers, conn=conn)
    input_digest = _input_digest(gathered, scope_json, budget_json)
    pack_id = compute_pack_id(req.pack_type, scope_json=scope_json, budget_json=budget_json,
                              input_digest=input_digest)
    ordered, acct = _apply_budget(gathered, req.budget)
    rows = [pi.to_row(pack_id) for pi in ordered]
    output_digest = _output_digest(rows)
    source_ids = {pi.source_id for pi in ordered if pi.included and pi.source_id}
    receipt_ids = {pi.receipt_id for pi in gathered if pi.receipt_id}
    claim_ct = sum(1 for pi in ordered if pi.included and pi.item_type == ITEM_CLAIM_CANDIDATE)
    header = {
        "pack_id": pack_id,
        "pack_type": req.pack_type,
        "title": req.title,
        "objective": req.objective,
        "scope_json": scope_json,
        "budget_json": budget_json,
        "status": "built",
        "created_by": req.created_by,
        "builder_version": BUILDER_VERSION,
        "input_digest": input_digest,
        "output_digest": output_digest,
        "source_count": len(source_ids),
        "claim_count": claim_ct,
        "receipt_count": len(receipt_ids),
        "item_count": len(rows),
        "truncated": acct["truncated"],
        "stale_count": acct["stale_count"],
    }
    pack_receipt = {
        "builder_version": BUILDER_VERSION,
        "input_digest": input_digest,
        "output_digest": output_digest,
        "scope_json": scope_json,
        "budget_json": budget_json,
        "included_count": acct["included_count"],
        "excluded_count": acct["excluded_count"],
        "source_count": len(source_ids),
        "claim_count": claim_ct,
        "receipt_count": len(receipt_ids),
        "stale_count": acct["stale_count"],
        "truncated": acct["truncated"],
        "total_chars": acct["total_chars"],
        "total_token_estimate": acct["total_token_estimate"],
    }
    return {"pack_id": pack_id, "header": header, "item_rows": rows, "receipt": pack_receipt}


def preview_context_pack(request: PackRequest, providers: Providers, *,
                         conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Assemble a pack WITHOUT persisting. Fully read-only. Status is reported as ``draft``."""
    assembled = _assemble(request, providers, conn=conn)
    header = dict(assembled["header"])
    header["status"] = "draft"
    return {"pack": header, "items": assembled["item_rows"], "receipt": assembled["receipt"]}


def build_context_pack(request: PackRequest, providers: Providers,
                       pack_repo: Any, *, apply: bool = False,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Assemble and — only when ``apply`` — persist the pack into the context-pack tables.

    Idempotent by ``pack_id``: if a pack with the same inputs already exists it is reported as
    ``reused`` (never overwritten). ``apply=False`` writes nothing.
    """
    assembled = _assemble(request, providers, conn=conn)
    pack_id = assembled["pack_id"]
    if not apply:
        header = dict(assembled["header"])
        header["status"] = "draft"
        return {"applied": False, "pack_id": pack_id, "pack": header,
                "items": assembled["item_rows"], "receipt": assembled["receipt"]}
    existing = pack_repo.get_pack(pack_id, conn=conn)
    if existing is not None:
        return {"applied": False, "reused": True, "pack_id": pack_id, "pack": existing}
    pack_repo.persist_pack(assembled["header"], assembled["item_rows"], assembled["receipt"],
                           conn=conn)
    return {"applied": True, "reused": False, "pack_id": pack_id,
            "pack": pack_repo.get_pack(pack_id, conn=conn),
            "item_count": len(assembled["item_rows"])}


def export_context_pack(pack: dict[str, Any], items: list[dict[str, Any]], *,
                        fmt: str = "json") -> dict[str, Any]:
    """Bounded export of a persisted pack. JSON only; relative paths only; no raw prompts/responses,
    no raw email bodies, no unbounded content (items already store bounded excerpts)."""
    if fmt != "json":
        raise ContextPackValidationError(f"unsupported_export_format:{fmt}")
    return {
        "format": "json",
        "pack": {k: pack.get(k) for k in (
            "pack_id", "pack_type", "title", "objective", "status", "builder_version",
            "input_digest", "output_digest", "source_count", "claim_count", "receipt_count",
            "item_count", "truncated", "stale_count", "created_at")},
        "items": [
            {k: it.get(k) for k in (
                "item_order", "item_type", "source_id", "note_rel_path", "claim_id", "job_id",
                "receipt_id", "title", "content_excerpt", "evidence_excerpt", "result_digest",
                "source_state", "confidence", "review_tier", "token_estimate", "included",
                "exclusion_reason")}
            for it in items
        ],
        "count": len(items),
    }


def mark_context_pack_stale_if_needed(pack_id: str, request: PackRequest, providers: Providers,
                                      pack_repo: Any, *,
                                      conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Explicit live check: re-derive the input digest for this pack's scope/budget and compare to
    the stored one. If drifted, mark the pack stale (explicit) and report. Never runs in the
    background; no automatic scan exists."""
    existing = pack_repo.get_pack(pack_id, conn=conn)
    if existing is None:
        return {"pack_id": pack_id, "found": False}
    assembled = _assemble(request, providers, conn=conn)
    current_digest = assembled["header"]["input_digest"]
    stored_digest = existing.get("input_digest")
    drifted = current_digest != stored_digest
    if drifted and existing.get("status") != "stale":
        pack_repo.mark_pack_stale(pack_id, detail="input_digest_drift", conn=conn)
    return {"pack_id": pack_id, "found": True, "stale": drifted,
            "stored_input_digest": stored_digest, "current_input_digest": current_digest}
