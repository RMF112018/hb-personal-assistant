"""Phase 09 Prompt 10 — cross-source relationship-quality mart tests.

Exercises the read-only relationship-quality mart + proof over controlled populations seeded via
ConstructionStore: a normal mixed population (link ratios / confidence distribution / guard-clean),
an empty substrate (fail-soft — relationship-quality has no external policy seed, so the
"missing-policy" canonical path is represented by the absent-substrate case), a stale-schema DB, a
no-raw injection (fail-closed; value never echoed; DB unchanged), and an orphan + duplicate signal
case. No live model call, no vault write, no external writeback.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.relationship_quality_mart import (
    build_relationship_quality_mart,
    build_relationship_quality_proof,
)
from hb_assistant.construction.store import ConstructionStore

_REF = json.dumps({"project_key": "P1"})


def _seed(db_path: str) -> ConstructionStore:
    """Seed a mixed candidate/relationship population with one promoted edge + evidence trail."""
    store = ConstructionStore(db_path)
    store.upsert_source_evidence_trail(
        evidence_trail_id="et-1",
        evidence_kind="document_relationship",
        source_refs_json=json.dumps(["doc-1#hash"]),
        confidence_class="deterministic",
        project_key="P1",
    )
    # Two candidates: one deterministic (promoted), one weak heuristic + sensitive + review-required.
    store.upsert_cross_source_relationship_candidate(
        candidate_id="cand-1",
        source_family="document",
        source_record_type="document",
        source_record_ref="doc-1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi-1-hash",
        relationship_type="document_record_reference",
        confidence_score=0.97,
        confidence_class="deterministic",
        source_reference_json=_REF,
        project_key="P1",
        deterministic=True,
        review_required=False,
        promotion_status="promoted",
        evidence_trail_id="et-1",
    )
    store.upsert_cross_source_relationship_candidate(
        candidate_id="cand-2",
        source_family="email",
        source_record_type="message",
        source_record_ref="msg-1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi-2-hash",
        relationship_type="email_record_reference",
        confidence_score=0.41,
        confidence_class="weak_heuristic",
        source_reference_json=_REF,
        project_key="P1",
        model_proposed=True,
        sensitive_high_impact=True,
        review_required=True,
        promotion_status="candidate",
        evidence_trail_id="et-1",
    )
    # One promoted relationship with full provenance (candidate + evidence trail).
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
        source_family="document",
        source_record_type="document",
        source_record_ref="doc-1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi-1-hash",
        relationship_type="document_record_reference",
        confidence_class="deterministic",
        source_reference_json=_REF,
        candidate_id="cand-1",
        project_key="P1",
        promotion_status="promoted",
        promoted_by="deterministic",
        evidence_trail_id="et-1",
    )
    return store


def test_normal_population_link_ratios_and_guard_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "rel.sqlite3")
    _seed(db)
    proof = build_relationship_quality_proof(db)
    mart = proof["mart"]

    assert proof["proof_passed"] is True
    assert proof["guard_violation"] is False
    assert proof["raw_content_findings"] == []
    assert mart["populated"] is True
    cand = mart["candidates"]
    assert cand["total"] == 2
    assert cand["by_confidence_class"]["deterministic"] == 1
    assert cand["by_confidence_class"]["weak_heuristic"] == 1
    assert cand["sensitive_high_impact"] == 1
    assert cand["link_ratios"]["promoted_share"] == 0.5  # 1 of 2 promoted
    assert mart["relationships"]["total"] == 1
    assert mart["promotion_rate_candidates_to_relationships"] == 0.5
    # Full provenance → no orphans, no multi-edge.
    assert mart["orphan_duplicate"]["orphan_total"] == 0
    assert mart["orphan_duplicate"]["multi_edge_pairs"] == 0


def test_empty_substrate_is_fail_soft(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.sqlite3")
    ConstructionStore(db)  # migrate, no relationship rows
    proof = build_relationship_quality_proof(db)
    mart = proof["mart"]

    assert mart["populated"] is False
    assert mart["candidates"]["total"] == 0
    assert mart["relationships"]["total"] == 0
    assert proof["guard_violation"] is False  # vacuously clean
    assert proof["proof_passed"] is True  # tables present + guard-clean + no raw on an empty substrate


def test_stale_schema_is_handled_gracefully(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite3")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_relationship_quality_proof(db)
    assert proof["schema_version"] == 5
    assert proof["schema_ok"] is False
    assert proof["proof_passed"] is False
    assert proof["mart"]["populated"] is False  # relationship tables absent on a stale schema


def test_raw_content_injection_fails_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "tainted.sqlite3")
    _seed(db)
    before = build_relationship_quality_mart(db)["candidates"]["total"]
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE cross_source_relationship_candidates SET signals_json = ? WHERE candidate_id = 'cand-1'",
        ("https://example.com/file?sig=abcdef0123456789abcdef",),
    )
    conn.commit()
    conn.close()

    proof = build_relationship_quality_proof(db)
    assert proof["proof_passed"] is False
    assert "cross_source_relationship_candidates.signals_json" in proof["raw_content_findings"]
    # The offending value is never echoed back — only the table.column location.
    assert "sig=abcdef" not in json.dumps(proof)
    # The read-only proof never mutates the DB (no-writeback): candidate count unchanged.
    after = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM cross_source_relationship_candidates"
    ).fetchone()[0]
    assert after == before == 2


def test_orphan_and_duplicate_signals(tmp_path: Path) -> None:
    db = str(tmp_path / "orphan.sqlite3")
    store = _seed(db)
    # A promoted relationship with NO candidate provenance (candidate_id NULL — the real orphan
    # shape, since a dangling FK value is rejected) and no evidence trail.
    store.upsert_cross_source_relationship(
        relationship_id="rel-orphan",
        source_family="calendar",
        source_record_type="event",
        source_record_ref="evt-9",
        target_family="email",
        target_record_type="thread",
        target_record_ref="thr-9-hash",
        relationship_type="meeting_email_correlation",
        confidence_class="weak_heuristic",
        source_reference_json=_REF,
        project_key="P1",
        promotion_status="promoted",
        promoted_by="deterministic",
    )
    # A second candidate on the SAME source→target pair as cand-1 but a different relationship_type
    # → a multi-edge (near-duplicate) pair.
    store.upsert_cross_source_relationship_candidate(
        candidate_id="cand-dup",
        source_family="document",
        source_record_type="document",
        source_record_ref="doc-1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi-1-hash",
        relationship_type="document_supersedes",
        confidence_score=0.6,
        confidence_class="weak_heuristic",
        source_reference_json=_REF,
        project_key="P1",
        evidence_trail_id="et-1",
    )

    proof = build_relationship_quality_proof(db)
    mart = proof["mart"]
    od = mart["orphan_duplicate"]
    assert od["promoted_missing_candidate"] >= 1
    assert od["relationship_evidence_unreachable"] >= 1
    assert od["orphan_total"] >= 1
    assert od["multi_edge_pairs"] >= 1
    assert any("orphan_total" in w for w in mart["warnings"])
    assert any("multi_edge_pairs" in w for w in mart["warnings"])
    # Orphans / duplicates are advisory signals — they do not fail the proof.
    assert proof["proof_passed"] is True
