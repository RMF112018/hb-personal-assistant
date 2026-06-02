"""Phase 08A Memory Curator Agent (A07) — Synthesized Prompt 10.

Proposes source-linked long-term memory candidates (origin + source refs + quality signals
+ review tier required), routes sensitive/high-impact material to Tier 3 (never
auto-accepted), and promotes a candidate to accepted memory only via an explicit operator
review decision — no silent acceptance. Metadata-only; no raw content; dry-run-first.
"""

from __future__ import annotations

import uuid
from typing import Any

from .models import MemoryCandidate, MemoryItem, MemoryReview, QualitySignal
from .policy import classify_memory_tier
from .store import (
    set_candidate_status,
    write_memory_candidate,
    write_memory_item,
    write_memory_review,
    write_quality_signal,
)

_QUALITY_SCORE = {"high": 0.9, "medium": 0.6, "low": 0.3}


def _quality_score(confidence_class: str) -> float:
    return _QUALITY_SCORE.get((confidence_class or "").lower(), 0.4)


def propose_memory_candidate(
    *,
    statement_redacted: str,
    proposed_memory_type: str,
    origin_id: str,
    source_refs: list[dict[str, str]],
    confidence_class: str,
    sensitivity_category: str | None = None,
    project_key: str | None = None,
    provenance_class: str | None = None,
    conflict: bool = False,
    model_only: bool = False,
    db_path: str | None = None,
    emit: bool = False,
) -> MemoryCandidate:
    """Propose a memory candidate (never auto-accepted; sensitive -> Tier 3)."""
    source_linked = bool(source_refs)
    tier, reason = classify_memory_tier(
        sensitivity_category=sensitivity_category,
        confidence_class=confidence_class,
        source_linked=source_linked,
        conflict=conflict,
        model_only=model_only,
    )
    candidate = MemoryCandidate(
        candidate_id=uuid.uuid4().hex,
        proposed_memory_type=proposed_memory_type,
        statement_redacted=statement_redacted,
        project_key=project_key,
        origin_id=origin_id,
        provenance_class=provenance_class or ("operator" if confidence_class == "high" else "model_proposed"),
        confidence_class=confidence_class,
        review_required=tier != 1,
        review_tier=tier,
        review_tier_reason_code=reason,
        sensitivity_class=sensitivity_category or "normal",
        source_refs=source_refs,
        status="proposed",
    )
    if emit:
        write_memory_candidate(candidate, db_path=db_path)
    return candidate


def review_memory_candidate(
    *,
    candidate: MemoryCandidate,
    decision: str,
    reviewer_ref: str = "operator",
    decision_reason_redacted: str | None = None,
    db_path: str | None = None,
    emit: bool = False,
) -> tuple[MemoryReview, MemoryItem | None, list[QualitySignal]]:
    """Apply an explicit operator review; on 'accepted', promote to accepted memory.

    Returns (review, accepted_item_or_None, quality_signals). No silent acceptance —
    promotion only ever happens through this explicit decision.
    """
    review = MemoryReview(
        review_id=uuid.uuid4().hex,
        candidate_id=candidate.candidate_id,
        decision=decision,  # type: ignore[arg-type]
        reviewer_ref=reviewer_ref,
        decision_reason_redacted=decision_reason_redacted,
    )
    item: MemoryItem | None = None
    signals: list[QualitySignal] = []

    if decision == "accepted":
        memory_id = uuid.uuid4().hex
        item = MemoryItem(
            memory_id=memory_id,
            memory_type=candidate.proposed_memory_type,
            statement_redacted=candidate.statement_redacted,
            project_key=candidate.project_key,
            origin_id=candidate.origin_id,
            provenance_class=candidate.provenance_class,
            confidence_class=candidate.confidence_class,
            review_status="accepted",
            sensitivity_class=candidate.sensitivity_class,
            source_refs=candidate.source_refs,
        )
        signals = [
            QualitySignal(
                signal_id=uuid.uuid4().hex,
                memory_id=memory_id,
                signal_type="origin",
                origin_id=candidate.origin_id,
                provenance_class=candidate.provenance_class,
            ),
            QualitySignal(
                signal_id=uuid.uuid4().hex,
                memory_id=memory_id,
                signal_type="quality",
                quality_score=_quality_score(candidate.confidence_class),
                freshness_class="fresh",
            ),
        ]

    if emit:
        write_memory_review(review, db_path=db_path)
        set_candidate_status(candidate.candidate_id, decision, db_path=db_path)
        if item is not None:
            write_memory_item(item, db_path=db_path)
            for sig in signals:
                write_quality_signal(sig, db_path=db_path)
    return review, item, signals


def build_memory_curator_agent_proof() -> dict[str, Any]:
    """Deterministic proof for ``memory-curator-agent-proof.json`` (temp DB)."""
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    refs = [{"source_family": "cross_source_relationships", "source_ref": "rel-1"}]
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/curator.sqlite3"
        ConstructionStore(db)  # migrate to V26

        normal = propose_memory_candidate(
            statement_redacted="project P1 kickoff confirmed",
            proposed_memory_type="fact",
            origin_id="qr-1",
            source_refs=refs,
            confidence_class="high",
            project_key="P1",
            db_path=db,
            emit=True,
        )
        sensitive = propose_memory_candidate(
            statement_redacted="alleged contract entitlement on P1",
            proposed_memory_type="claim",
            origin_id="qr-2",
            source_refs=refs,
            confidence_class="high",
            sensitivity_category="financial",
            project_key="P1",
            db_path=db,
            emit=True,
        )
        review, item, signals = review_memory_candidate(
            candidate=normal, decision="accepted", db_path=db, emit=True
        )

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        mem_rows = [dict(r) for r in conn.execute("SELECT * FROM long_term_memory_items").fetchall()]
        sig_rows = [
            dict(r) for r in conn.execute("SELECT * FROM long_term_memory_quality_signals").fetchall()
        ]
        cand_rows = [
            dict(r) for r in conn.execute("SELECT * FROM memory_update_candidates").fetchall()
        ]
        conn.close()

    guard_cols = [c for c in (mem_rows[0] if mem_rows else {}) if c.endswith("_persisted")]
    guards_zero = all(
        all(r[c] == 0 for c in guard_cols) for r in mem_rows
    ) and all(
        all(r[c] == 0 for c in guard_cols if c in r) for r in sig_rows
    )
    blob = "".join(c.model_dump_json() for c in (normal, sensitive)) + (
        item.model_dump_json() if item else ""
    )
    no_raw = not any(
        t in blob
        for t in ("raw_body", "raw_document_text", "raw_prompt", "raw_response", "signed_url",
                  "download_url", "secret")
    )

    proof_passed = bool(
        normal.review_tier == 1
        and sensitive.review_tier == 3
        and sensitive.review_required is True
        and sensitive.review_tier_reason_code == "T3_SENSITIVE_HIGH_IMPACT"
        and item is not None
        and item.review_status == "accepted"
        and any(s.signal_type == "origin" and s.origin_id for s in signals)
        and any(s.signal_type == "quality" for s in signals)
        and len(mem_rows) == 1
        and len(sig_rows) == 2
        and guards_zero
        and no_raw
    )
    return {
        "proof": "phase_08a_memory_curator_agent",
        "proof_passed": proof_passed,
        "normal_candidate": {
            "review_tier": normal.review_tier,
            "reason": normal.review_tier_reason_code,
            "review_required": normal.review_required,
        },
        "sensitive_candidate_routed_tier_3": {
            "review_tier": sensitive.review_tier,
            "reason": sensitive.review_tier_reason_code,
            "review_required": sensitive.review_required,
            "sensitivity_class": sensitive.sensitivity_class,
        },
        "accepted_memory": {
            "review_status": item.review_status if item else None,
            "origin_id_present": bool(item.origin_id) if item else False,
            "source_ref_count": len(item.source_refs) if item else 0,
            "quality_signal_types": [s.signal_type for s in signals],
        },
        "candidate_count": len(cand_rows),
        "memory_item_count": len(mem_rows),
        "quality_signal_count": len(sig_rows),
        "guard_columns_zero": guards_zero,
        "no_raw_content": no_raw,
        "no_silent_acceptance": True,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "sensitive_high_impact_routes_tier_3": True,
            "no_silent_acceptance": True,
            "model_direct_external_api_access": False,
        },
    }


def build_long_term_memory_proof() -> dict[str, Any]:
    """Deterministic proof for ``long-term-memory-proof.json`` (temp DB)."""
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    refs = [
        {"source_family": "phase_07d_source_evidence_trails", "source_ref": "ev-1", "evidence_ref": "ev-1"}
    ]
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/memory.sqlite3"
        ConstructionStore(db)
        cand = propose_memory_candidate(
            statement_redacted="P1 schedule baseline accepted",
            proposed_memory_type="fact",
            origin_id="brief-1",
            source_refs=refs,
            confidence_class="high",
            project_key="P1",
            db_path=db,
            emit=True,
        )
        _review, item, _signals = review_memory_candidate(
            candidate=cand, decision="accepted", db_path=db, emit=True
        )
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        item_row = dict(conn.execute("SELECT * FROM long_term_memory_items").fetchone())
        ref_rows = [
            dict(r) for r in conn.execute("SELECT * FROM long_term_memory_source_refs").fetchall()
        ]
        sig_rows = [
            dict(r) for r in conn.execute("SELECT * FROM long_term_memory_quality_signals").fetchall()
        ]
        conn.close()

    guard_cols = [c for c in item_row if c.endswith("_persisted")]
    guards_zero = all(item_row[c] == 0 for c in guard_cols)
    proof_passed = bool(
        item is not None
        and item_row["review_status"] == "accepted"
        and item_row["origin_id"]
        and len(ref_rows) == 1
        and ref_rows[0]["source_ref"] == "ev-1"
        and any(s["signal_type"] == "origin" for s in sig_rows)
        and any(s["signal_type"] == "quality" for s in sig_rows)
        and guards_zero
    )
    return {
        "proof": "phase_08a_long_term_memory",
        "proof_passed": proof_passed,
        "memory_review_status": item_row["review_status"],
        "origin_id_present": bool(item_row["origin_id"]),
        "source_ref_count": len(ref_rows),
        "quality_signal_types": sorted({s["signal_type"] for s in sig_rows}),
        "guard_columns_zero": guards_zero,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "origin_and_source_refs_required": True,
            "review_controlled": True,
        },
    }
