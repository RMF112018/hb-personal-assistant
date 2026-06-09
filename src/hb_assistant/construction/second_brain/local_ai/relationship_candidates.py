"""Phase 10 — relationship candidate engine (deterministic, source-linked, no writeback).

Cross-source context enrichment for the local-agent family: links already-ingested email
threads and calendar events into reviewable ``phase10_relationship_candidates`` rows using the
existing deterministic ``relationship_scoring`` layer. A local model never decides relatedness.

Design contract (locked in package prompt 01):
- Relationship type: ``email_calendar`` only. Procore relations are DEFERRED — the deterministic
  scorer is email↔calendar only and no safe Procore source-linking read-model exists yet.
- Identity / idempotency: ``relationship_candidate_id = sha256(type|from_family|from_ref_hash|
  to_family|to_ref_hash)[:32]``. Source refs are hashed with the repo-standard ``hash_value``
  (sha256, no salt → stable across runs and DB copies). Re-run yields ``skipped_existing``.
- Persistence stores ONLY hashed source refs + safe reason codes; the 13 guard columns are left to
  DEFAULT 0 / CHECK(=0). No raw subjects, bodies, addresses, join URLs, prompts, or responses.
- Dry-run is the default (zero writes). ``--apply`` (dry_run=False) requires ``max_persist`` and
  caps ACTUAL inserts; weak relationships are excluded by ``min_confidence`` (default moderate).
- Deterministic order everywhere: confidence DESC, then ``relationship_candidate_id`` ASC.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from hb_assistant.normalize.redaction import hash_value

from .relationship_scoring import MODERATE_THRESHOLD, find_email_calendar_relationships


def _candidate_id(
    relationship_type: str,
    from_source_family: str,
    from_source_ref_hash: str,
    to_source_family: str,
    to_source_ref_hash: str,
) -> str:
    """Deterministic, collision-resistant id from type + hashed source-ref pair."""
    basis = "|".join(
        (
            relationship_type,
            from_source_family,
            from_source_ref_hash,
            to_source_family,
            to_source_ref_hash,
        )
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def _safe_candidate(rel: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Project a scorer result into a safe, persistable candidate.

    Returns ``None`` if either source ref is missing (cannot be source-linked safely).
    The output carries hashed refs only — never the raw thread_ref / event_index_id.
    """
    from_ref = rel.get("from_source_ref")
    to_ref = rel.get("to_source_ref")
    if not from_ref or not to_ref:
        return None
    from_hash = hash_value(str(from_ref))
    to_hash = hash_value(str(to_ref))
    if not from_hash or not to_hash:
        return None
    rel_type = str(rel.get("relationship_type") or "email_calendar")
    from_family = str(rel.get("from_source_family") or "")
    to_family = str(rel.get("to_source_family") or "")
    cid = _candidate_id(rel_type, from_family, from_hash, to_family, to_hash)
    reason_codes = [str(c) for c in (rel.get("reason_codes") or [])]
    return {
        "relationship_candidate_id": cid,
        "relationship_type": rel_type,
        "from_source_family": from_family,
        "from_source_ref_hash": from_hash,
        "to_source_family": to_family,
        "to_source_ref_hash": to_hash,
        "project_key": rel.get("project_key"),
        "confidence": float(rel.get("confidence") or 0.0),
        "confidence_class": str(rel.get("relationship_class") or "weak"),
        "review_required": bool(rel.get("review_required")),
        "reason_codes": reason_codes,
        "reason_redacted": ",".join(reason_codes) if reason_codes else None,
    }


def build_relationship_candidates(
    *,
    store: Any,
    now_utc: str,
    project_key: Optional[str] = None,
    limit: int = 50,
    scan_threads: int = 50,
    scan_events: int = 50,
    min_confidence: float = MODERATE_THRESHOLD,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
) -> dict[str, Any]:
    """Scan email↔calendar pairs and build/persist deterministic relationship candidates.

    Dry-run is the default (zero writes). ``--apply`` (dry_run=False) requires ``max_persist`` and
    caps ACTUAL inserts into ``phase10_relationship_candidates``; once the cap is hit, remaining new
    candidates are counted (``would_persist``) but not written. Idempotent on
    ``relationship_candidate_id``. Weak relationships are excluded by ``min_confidence``.
    Relatedness is decided ONLY by the deterministic scorer — no model call.
    """
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual persisted candidates)")

    rels = find_email_calendar_relationships(
        store=store,
        project_key=project_key,
        limit=limit,
        scan_threads=scan_threads,
        scan_events=scan_events,
        min_confidence=min_confidence,
    )

    existing_ids = store.list_phase10_relationship_candidate_ids()

    # Project to safe candidates; drop pairs with missing/unhashable source refs. De-dupe by id
    # (a bounded scan should not collide, but guard for stability), keeping the highest confidence.
    candidates: dict[str, dict[str, Any]] = {}
    skipped_missing_ref = 0
    for rel in rels:
        cand = _safe_candidate(rel)
        if cand is None:
            skipped_missing_ref += 1
            continue
        cid = cand["relationship_candidate_id"]
        prev = candidates.get(cid)
        if prev is None or cand["confidence"] > prev["confidence"]:
            candidates[cid] = cand

    # Deterministic order: confidence DESC, then candidate id ASC.
    ordered = sorted(
        candidates.values(),
        key=lambda c: (-c["confidence"], c["relationship_candidate_id"]),
    )

    summary = {
        "scanned_relationships": len(rels),
        "candidates": len(ordered),
        "would_persist": 0,
        "persisted": 0,
        "skipped_existing": 0,
        "skipped_capped": 0,
        "skipped_missing_ref": skipped_missing_ref,
        "review_required": sum(1 for c in ordered if c["review_required"]),
    }
    by_class: dict[str, int] = {}
    remaining: Optional[int] = max_persist if (not dry_run and max_persist is not None) else None

    for c in ordered:
        by_class[c["confidence_class"]] = by_class.get(c["confidence_class"], 0) + 1
        if c["relationship_candidate_id"] in existing_ids:
            summary["skipped_existing"] += 1
            continue
        summary["would_persist"] += 1
        if dry_run:
            continue
        if remaining is not None and remaining <= 0:
            summary["skipped_capped"] += 1
            continue
        inserted = store.insert_phase10_relationship_candidate(
            relationship_candidate_id=c["relationship_candidate_id"],
            from_source_family=c["from_source_family"],
            from_source_ref_hash=c["from_source_ref_hash"],
            to_source_family=c["to_source_family"],
            to_source_ref_hash=c["to_source_ref_hash"],
            relationship_type=c["relationship_type"],
            confidence=c["confidence"],
            confidence_class=c["confidence_class"],
            project_key=c["project_key"],
            deterministic=True,
            model_proposed=False,
            review_status="pending",
            reason_redacted=c["reason_redacted"],
        )
        if inserted:
            summary["persisted"] += 1
            existing_ids.add(c["relationship_candidate_id"])
            if remaining is not None:
                remaining -= 1
        else:
            summary["skipped_existing"] += 1

    # Output relationships: safe fields only (hashed refs, codes) — never raw refs/content.
    out_relationships = [
        {
            "relationship_candidate_id": c["relationship_candidate_id"],
            "relationship_type": c["relationship_type"],
            "from_source_family": c["from_source_family"],
            "from_source_ref_hash": c["from_source_ref_hash"],
            "to_source_family": c["to_source_family"],
            "to_source_ref_hash": c["to_source_ref_hash"],
            "project_key": c["project_key"],
            "confidence": c["confidence"],
            "confidence_class": c["confidence_class"],
            "review_required": c["review_required"],
            "reason_codes": c["reason_codes"],
        }
        for c in ordered
    ]

    return {
        "command": "second-brain relationship-candidates scan",
        "ok": True,
        "applied": not dry_run,
        "now_utc": now_utc,
        "relationship_types": ["email_calendar"],
        "deferred_relationship_types": ["email_procore", "calendar_procore"],
        "min_confidence": float(min_confidence),
        "summary": summary,
        "by_class": dict(sorted(by_class.items())),
        "relationships": out_relationships,
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "deterministic_no_model": True,
            "model_does_not_decide_relatedness": True,
            "source_linked_hashed_refs_only": True,
            "no_raw_persistence": True,
            "no_writeback": True,
            "weak_excluded": True,
            "advisory_only": True,
        },
    }
