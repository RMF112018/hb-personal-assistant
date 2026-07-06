"""N8C-6 enrichment-review read model — DERIVED, no table of its own.

Turns N8C-5 enrichment receipts (V101) + N8C-4 candidate claims (V100) + N8C-2 identity state into
bounded, source-linked **review items** that say *what needs review and why*. Pure read model: it
never writes, never accepts a claim, never mutates a claim's ``review_state``. The advisory
``review_tier`` here is distinct from a claim's ``review_state`` — candidate claims stay
``candidate``/``unreviewed``.

DB-only (no vault read) so it also works over the read-only MCP snapshot. Source integrity is derived
from the index rows (``deleted`` flag, card ``generation_status``, reverse-lookup ambiguity), not from
a vault stat.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import source_card_identity as identity
from .context_pack_models import (
    EVIDENCE_HARD_CAP,
    bound_text,
    clamp_confidence,
    sha256_hex,
)

# Below this model confidence a summary/claim/link is flagged for a human rather than trusted.
LOW_CONFIDENCE_THRESHOLD = 0.4
SUMMARY_EXCERPT_CAP = 2_000

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200

# Review tiers (advisory).
TIER_SAFE_SUMMARY = "safe_summary"
TIER_NEEDS_OPERATOR_REVIEW = "needs_operator_review"
TIER_SOURCE_STALE = "source_stale"
TIER_CLAIM_CANDIDATE = "claim_candidate"
TIER_LINK_CANDIDATE = "link_candidate"
TIER_LOW_CONFIDENCE = "low_confidence"

# Review item types.
ITEM_SOURCE_SUMMARY = "source_summary"
ITEM_CLAIM_CANDIDATE = "claim_candidate"
ITEM_BACKLINK_SUGGESTION = "backlink_suggestion"
ITEM_UNKNOWN = "unknown"

# Source-integrity states this model derives (DB-only).
SRC_CURRENT = "current"
SRC_STALE = "stale"
SRC_MISSING = "missing"
SRC_DELETED = "source_deleted"


def _clamp_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


def compute_review_item_id(kind: str, key: str) -> str:
    return sha256_hex(f"{kind}|{key}")[:24]


def _source_state(source_repo: Any, source_id: str | None, *,
                  conn: sqlite3.Connection | None) -> str:
    """DB-only source integrity: missing / source_deleted / stale / current."""
    if not source_id:
        return SRC_CURRENT
    detail = source_repo.get_source_detail(source_id, conn=conn)
    if detail is None:
        return SRC_MISSING
    if detail.get("deleted"):
        return SRC_DELETED
    cards = source_repo.list_cards_for_source(source_id, conn=conn)
    if any(c.get("generation_status") == "stale" for c in cards):
        return SRC_STALE
    return SRC_CURRENT


def _resolution(source_repo: Any, note_rel_path: str | None, *,
                conn: sqlite3.Connection | None) -> str:
    """Reverse-lookup ambiguity for a card path: none / unique / ambiguous."""
    if not note_rel_path:
        return "none"
    return identity.get_source_for_card(source_repo, note_rel_path, conn=conn).resolution


def classify_review_tier(*, item_type: str, confidence: float | None, source_state: str,
                         resolution: str) -> str:
    """Advisory tier. Source-integrity problems dominate, then low confidence, then item type.

    Nothing here accepts a claim or flips a review_state — it only labels why an item needs a look.
    """
    if resolution == "ambiguous":
        return TIER_NEEDS_OPERATOR_REVIEW
    if source_state in (SRC_DELETED, SRC_MISSING, SRC_STALE):
        return TIER_SOURCE_STALE
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        return TIER_LOW_CONFIDENCE
    if item_type == ITEM_CLAIM_CANDIDATE:
        return TIER_CLAIM_CANDIDATE
    if item_type == ITEM_BACKLINK_SUGGESTION:
        return TIER_LINK_CANDIDATE
    if item_type == ITEM_SOURCE_SUMMARY:
        return TIER_SAFE_SUMMARY
    return TIER_NEEDS_OPERATOR_REVIEW


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _items_from_receipt(receipt: dict[str, Any], enrichment_repo: Any, claim_repo: Any,
                        source_repo: Any, *,
                        conn: sqlite3.Connection | None) -> list[dict[str, Any]]:
    job_type = receipt.get("job_type")
    receipt_id = receipt.get("receipt_id")
    job_id = receipt.get("job_id")
    source_id = None  # receipts don't carry source_id directly; recover it via the job
    note_rel_path = None
    result = _loads(receipt.get("result_json"))
    result_digest = receipt.get("output_digest")

    # The job carries the subject anchor; look it up once via the enrichment repo.
    job_row = enrichment_repo.get_job(job_id, conn=conn) if job_id else None
    if job_row:
        source_id = job_row.get("source_id")
        note_rel_path = job_row.get("note_rel_path")
    src_state = _source_state(source_repo, source_id, conn=conn)
    resolution = _resolution(source_repo, note_rel_path, conn=conn)

    out: list[dict[str, Any]] = []
    if job_type == "source_summary":
        summary = result.get("summary")
        conf = clamp_confidence(result.get("confidence")) if result.get("confidence") is not None else None
        out.append(_item(
            item_type=ITEM_SOURCE_SUMMARY, kind="summary", key=str(receipt_id),
            receipt_id=receipt_id, job_id=job_id, job_type=job_type, source_id=source_id,
            note_rel_path=note_rel_path, claim_id=None, review_state="unreviewed",
            confidence=conf, summary=summary, evidence=None, result_digest=result_digest,
            source_state=src_state, resolution=resolution,
        ))
    elif job_type == "backlink_suggestions":
        for idx, sug in enumerate(result.get("suggestions", []) or []):
            if not isinstance(sug, dict):
                continue
            conf = clamp_confidence(sug.get("confidence")) if sug.get("confidence") is not None else None
            out.append(_item(
                item_type=ITEM_BACKLINK_SUGGESTION, kind="backlink", key=f"{receipt_id}|{idx}",
                receipt_id=receipt_id, job_id=job_id, job_type=job_type, source_id=source_id,
                note_rel_path=note_rel_path, claim_id=None, review_state="unreviewed",
                confidence=conf, summary=sug.get("reason"), evidence=sug.get("target"),
                result_digest=result_digest, source_state=src_state, resolution=resolution,
            ))
    elif job_type == "claim_extraction":
        # Link to the actual candidate claim rows for this source (they stay candidate/unreviewed).
        claims = claim_repo.get_claims_for_source(source_id, limit=_MAX_LIMIT, conn=conn) \
            if source_id else []
        for cl in claims:
            if cl.get("status") != "candidate":
                continue
            out.append(_item(
                item_type=ITEM_CLAIM_CANDIDATE, kind="claim", key=str(cl.get("claim_id")),
                receipt_id=receipt_id, job_id=job_id, job_type=job_type,
                source_id=cl.get("source_id"), note_rel_path=cl.get("note_rel_path"),
                claim_id=cl.get("claim_id"), review_state=cl.get("review_state") or "unreviewed",
                confidence=clamp_confidence(cl.get("confidence")), summary=cl.get("claim_text"),
                evidence=cl.get("evidence_excerpt"), result_digest=result_digest,
                source_state=cl.get("source_state") or src_state, resolution=resolution,
            ))
    return out


def _item(*, item_type: str, kind: str, key: str, receipt_id: Any, job_id: Any, job_type: Any,
          source_id: Any, note_rel_path: Any, claim_id: Any, review_state: str,
          confidence: float | None, summary: Any, evidence: Any, result_digest: Any,
          source_state: str, resolution: str) -> dict[str, Any]:
    tier = classify_review_tier(item_type=item_type, confidence=confidence,
                                source_state=source_state, resolution=resolution)
    return {
        "review_item_id": compute_review_item_id(kind, key),
        "review_item_type": item_type,
        "receipt_id": receipt_id,
        "job_id": job_id,
        "job_type": job_type,
        "source_id": source_id,
        "note_rel_path": note_rel_path,
        "claim_id": claim_id,
        "review_state": review_state,
        "review_tier": tier,
        "confidence": confidence,
        "summary": bound_text(summary, SUMMARY_EXCERPT_CAP) if summary else None,
        "evidence_excerpt": bound_text(evidence, EVIDENCE_HARD_CAP) if evidence else None,
        "result_digest": result_digest,
        "source_state": source_state,
    }


def list_enrichment_review_items(enrichment_repo: Any, claim_repo: Any, source_repo: Any, *,
                                 limit: int = _DEFAULT_LIMIT, job_type: str | None = None,
                                 review_tier: str | None = None,
                                 conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded, DB-derived review items over the most recent enrichment receipts.

    Returns the uniform ``{review_items, count, limit, truncated}`` envelope. ``truncated`` is True
    when more items were derived than ``limit`` returned.
    """
    lim = _clamp_limit(limit)
    # Read a bounded window of receipts; each may expand to several items (claims), so over-read.
    receipts = enrichment_repo.list_receipts(limit=min(_MAX_LIMIT, lim * 4 + 4), conn=conn)
    items: list[dict[str, Any]] = []
    for r in receipts:
        if job_type and r.get("job_type") != job_type:
            continue
        items.extend(_items_from_receipt(r, enrichment_repo, claim_repo, source_repo, conn=conn))
    if review_tier:
        items = [it for it in items if it.get("review_tier") == review_tier]
    truncated = len(items) > lim
    kept = items[:lim]
    return {"review_items": kept, "count": len(kept), "limit": lim, "truncated": truncated}


def get_enrichment_review_item(enrichment_repo: Any, claim_repo: Any, source_repo: Any,
                               review_item_id: str, *,
                               conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    """Re-derive the bounded review-item set and return the one matching ``review_item_id``."""
    env = list_enrichment_review_items(enrichment_repo, claim_repo, source_repo, limit=_MAX_LIMIT,
                                       conn=conn)
    for it in env["review_items"]:
        if it["review_item_id"] == review_item_id:
            return it
    return None
