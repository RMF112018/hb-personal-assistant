"""Phase 07D Prompt 03 — unified cross-source relationship substrate.

Proves the substrate builder normalizes the three existing edge-shaped per-source
relationship-candidate tables (document V24, calendar↔email V23, email V11) into the
unified V25 ``cross_source_relationship_candidates`` + ``source_evidence_trails`` tables:
dry-run writes nothing, apply is idempotent, weak/model/sensitive route to review and are
never promoted, no raw content / URL / token round-trips, and empty sources are safe.

Source tables carry FK chains to calendar/email/document parents; the substrate write-side
tables do not. Tests seed the source candidate rows via a raw connection (foreign keys off)
so the normalizer's read side has data without standing up the full parent chains.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from hb_assistant.construction.relationships.cross_source_substrate import (
    CrossSourceRelationshipSubstrateBuilder,
    relationship_substrate_status,
)
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}", re.IGNORECASE
)

# Eight guard columns that must stay 0 on every substrate row.
_GUARDS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_xsub_")
    import os

    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _seed_standard(db: str) -> None:
    """Seed four representative source candidates via a raw (FK-off) connection."""
    raw = sqlite3.connect(db)
    # document → procore (weak heuristic, origin review-required)
    raw.execute(
        "INSERT INTO construction_document_relationship_candidates "
        "(candidate_id, document_card_id, target_system, target_record_type, "
        "target_record_key_hash, relationship_type, candidate_type, confidence, "
        "confidence_class, review_required, promotion_status, source_reference_json) "
        "VALUES ('d1','card1','procore','rfi','h_rfi_1','document_record_reference',"
        "'heuristic',0.55,'moderate_heuristic',1,'candidate',?)",
        (json.dumps({"project_key": "tropical", "document_type": "rfi"}),),
    )
    # calendar ↔ email (strong heuristic, no review)
    raw.execute(
        "INSERT INTO meeting_email_relationship_candidates "
        "(candidate_id, event_index_id, thread_key_hash, candidate_type, source_reference_json, "
        "confidence, confidence_class, review_required, promotion_status, project_key) "
        "VALUES ('m1','ev1','th1','time_and_domain','{}',0.80,'strong',0,'candidate','tropical')"
    )
    # email → procore (strong heuristic, no review)
    raw.execute(
        "INSERT INTO email_relationship_candidates "
        "(candidate_id, message_id, candidate_type, match_signal, confidence, review_required, "
        "project_key, target_source_system, target_table, target_key) "
        "VALUES ('e1','msg1','procore_rfi','procore_notification',0.85,0,'tropical','procore',"
        "'procore_live_records','pk_hash_1')"
    )
    # email → project (financial → sensitive + review; null target_key exercises the hash fallback)
    raw.execute(
        "INSERT INTO email_relationship_candidates "
        "(candidate_id, message_id, candidate_type, match_signal, confidence, review_required, "
        "project_key, target_source_system) "
        "VALUES ('e2','msg2','financial_keyword_in_preview','financial_keyword_in_preview',0.60,"
        "1,'tropical','hb_construction')"
    )
    raw.commit()
    raw.close()


def test_build_apply_writes_candidates_and_evidence() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        report = CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        assert report["ok"] is True
        assert report["mode"] == "apply"
        assert report["summary"]["candidates_written"] == 4
        assert report["summary"]["evidence_trails_written"] == 4
        assert store.count_cross_source_relationship_candidates() == 4
        assert store.count_source_evidence_trails() == 4
        assert report["summary"]["by_source_family"] == {"calendar": 1, "document": 1, "email": 2}
    finally:
        Path(db).unlink(missing_ok=True)


def test_build_dry_run_writes_nothing_but_plans() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        report = CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=True)
        assert report["mode"] == "dry_run"
        assert report["summary"]["candidates_planned"] == 4
        assert report["summary"]["candidates_written"] == 0
        assert store.count_cross_source_relationship_candidates() == 0
        assert store.count_source_evidence_trails() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_build_is_idempotent() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        builder = CrossSourceRelationshipSubstrateBuilder(store)
        builder.build(dry_run=False)
        builder.build(dry_run=False)  # re-apply
        assert store.count_cross_source_relationship_candidates() == 4
        assert store.count_source_evidence_trails() == 4
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_and_sensitive_routing() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        by_family: dict[str, list[dict]] = {}
        for c in store.list_cross_source_relationship_candidates():
            by_family.setdefault(c["source_family"], []).append(c)
        # financial email candidate → sensitive_high_impact + review_required
        fin = [c for c in by_family["email"] if c["sensitive_high_impact"]]
        assert fin and fin[0]["review_required"] is True
        # the strong-heuristic, non-sensitive calendar edge → no review
        cal = by_family["calendar"][0]
        assert cal["confidence_class"] == "strong_heuristic"
        assert cal["review_required"] is False
        # weak-heuristic document edge with origin review → review_required
        doc = by_family["document"][0]
        assert doc["confidence_class"] == "weak_heuristic"
        assert doc["review_required"] is True
        # nothing is ever auto-promoted by build
        assert all(c["promotion_status"] == "candidate" for fam in by_family.values() for c in fam)
    finally:
        Path(db).unlink(missing_ok=True)


def test_build_never_writes_promoted_relationships() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        assert store.count_cross_source_relationships() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_raw_content_or_guard_violations() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        blob = json.dumps(
            store.list_cross_source_relationship_candidates() + store.list_source_evidence_trails()
        )
        assert not _LEAK.search(blob), "substrate rows contain a leak-pattern value"
        # all eight guard columns are 0 on every written row
        raw = sqlite3.connect(db)
        for table in ("cross_source_relationship_candidates", "source_evidence_trails"):
            cols = ", ".join(_GUARDS)
            for row in raw.execute(f"SELECT {cols} FROM {table}"):
                assert set(row) <= {0}, f"{table} has a non-zero guard column: {row}"
        raw.close()
    finally:
        Path(db).unlink(missing_ok=True)


def test_empty_sources_build_ok_zero() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        report = CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        assert report["ok"] is True
        assert report["summary"]["candidates_written"] == 0
        status = relationship_substrate_status(store)
        assert status["summary"]["candidates"] == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_status_reports_coverage_after_apply() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        status = relationship_substrate_status(store)
        assert status["summary"]["candidates"] == 4
        assert status["summary"]["evidence_trails"] == 4
        assert status["summary"]["promoted_relationships"] == 0
        assert status["summary"]["by_source_family"] == {"calendar": 1, "document": 1, "email": 2}
    finally:
        Path(db).unlink(missing_ok=True)


def test_project_filter_excludes_other_projects() -> None:
    db = _fresh_db()
    try:
        _seed_standard(db)
        store = ConstructionStore(db_path=db)
        report = CrossSourceRelationshipSubstrateBuilder(store).build(
            dry_run=True, project_filter="nonexistent"
        )
        assert report["summary"]["candidates_planned"] == 0
        assert report["summary"]["skipped_project_filter"] == 4
    finally:
        Path(db).unlink(missing_ok=True)


def test_cli_build_and_status_subprocess_exit_zero() -> None:
    """The CLI commands run (dry-run, non-mutating) and emit valid JSON with exit 0."""
    for sub in ("build", "status", "promote"):
        cmd = [
            sys.executable, "-m", "hb_assistant.cli.main",
            "construction-agent", "relationships", sub, "--json",
        ]
        proc = subprocess.run(
            cmd, cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=90,
        )
        assert proc.returncode == 0, f"{sub} failed: {proc.stderr[:500]}"
        payload = json.loads(proc.stdout)
        assert payload["command"] == f"construction-agent relationships {sub}"
        assert payload["report"]["ok"] is True


# --- Prompt 04: Procore-native + resolution-queue arms, alignment, promotion ----


def _seed_procore_and_resolution(db: str) -> None:
    """Seed Procore-native edges + relationship-resolution-queue edges via raw (FK-off) conn."""
    raw = sqlite3.connect(db)
    now = "2026-06-01T00:00:00Z"
    # deterministic record→record and record→entity edges
    raw.execute(
        "INSERT INTO procore_record_edges (edge_id, project_key, from_record_key, to_record_key, "
        "to_entity_key, edge_type, source_endpoint_id, confidence, first_seen_at_utc, "
        "last_seen_at_utc) VALUES ('pe1','tropical','rfis:100','submittals:200',NULL,'references',"
        "'rfis',1.0,?,?)",
        (now, now),
    )
    raw.execute(
        "INSERT INTO procore_record_edges (edge_id, project_key, from_record_key, to_record_key, "
        "to_entity_key, edge_type, source_endpoint_id, confidence, first_seen_at_utc, "
        "last_seen_at_utc) VALUES ('pe2','tropical','rfis:100',NULL,'entity_hash_abc',"
        "'assigned_to','rfis',1.0,?,?)",
        (now, now),
    )
    # resolution-queue edges: a strong-heuristic (no review) and a weak/safety (review)
    raw.execute(
        "INSERT INTO relationship_resolution_queue (relationship_id, from_canonical_record_id, "
        "to_canonical_record_id, from_source_system, to_source_system, relationship_type, "
        "relationship_status, confidence_class, confidence, review_required, promotion_status) "
        "VALUES ('rq1','procore:rfis:1','email:msg:9','procore','email','documents_discusses',"
        "'open','strong_heuristic',0.85,0,'not_promoted')"
    )
    raw.execute(
        "INSERT INTO relationship_resolution_queue (relationship_id, from_canonical_record_id, "
        "to_canonical_record_id, from_source_system, to_source_system, relationship_type, "
        "relationship_status, confidence_class, confidence, review_required, promotion_status) "
        "VALUES ('rq2','procore:rfis:2','calendar:ev:9','procore','calendar','safety_related',"
        "'open','weak_heuristic',0.40,1,'not_promoted')"
    )
    raw.commit()
    raw.close()


def test_procore_edges_normalize_as_deterministic() -> None:
    db = _fresh_db()
    try:
        _seed_procore_and_resolution(db)
        store = ConstructionStore(db_path=db)
        CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        by_target = {c["target_family"]: c for c in store.list_cross_source_relationship_candidates()}
        # record→record and record→entity both present, both deterministic
        assert "procore" in by_target and by_target["procore"]["confidence_class"] == "deterministic"
        assert "procore_entity" in by_target
        assert by_target["procore"]["deterministic"] is True
        assert by_target["procore"]["review_required"] is False
    finally:
        Path(db).unlink(missing_ok=True)


def test_resolution_queue_confidence_class_override_preserved() -> None:
    db = _fresh_db()
    try:
        _seed_procore_and_resolution(db)
        store = ConstructionStore(db_path=db)
        CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        rq = [
            c for c in store.list_cross_source_relationship_candidates()
            if c["target_family"] in ("email", "calendar")
        ]
        classes = {c["target_family"]: c for c in rq}
        assert classes["email"]["confidence_class"] == "strong_heuristic"
        assert classes["email"]["review_required"] is False
        # weak + safety keyword → sensitive + review
        assert classes["calendar"]["confidence_class"] == "weak_heuristic"
        assert classes["calendar"]["review_required"] is True
        assert classes["calendar"]["sensitive_high_impact"] is True
    finally:
        Path(db).unlink(missing_ok=True)


def test_project_key_alignment_backfills_from_source_record_map() -> None:
    db = _fresh_db()
    try:
        _seed_procore_and_resolution(db)
        raw = sqlite3.connect(db)
        # map the rq1 source canonical id to project 'gardens'; rq2 has no mapping
        raw.execute(
            "INSERT INTO source_system_record_map (canonical_record_id, project_key, source_system, "
            "source_table, source_primary_key, confidence_class) VALUES "
            "('c1','gardens','procore','procore_live_records','procore:rfis:1','deterministic')"
        )
        raw.commit()
        raw.close()
        store = ConstructionStore(db_path=db)
        report = CrossSourceRelationshipSubstrateBuilder(store).build(dry_run=False)
        assert report["summary"]["project_key_aligned"] == 1
        rows = {c["target_family"]: c for c in store.list_cross_source_relationship_candidates()}
        assert rows["email"]["project_key"] == "gardens"  # rq1 aligned
        assert rows["calendar"]["project_key"] is None  # rq2 unmapped
    finally:
        Path(db).unlink(missing_ok=True)


def test_promote_only_deterministic_non_sensitive() -> None:
    db = _fresh_db()
    try:
        _seed_procore_and_resolution(db)
        _seed_standard(db)  # adds a sensitive financial email + weak document, etc.
        store = ConstructionStore(db_path=db)
        builder = CrossSourceRelationshipSubstrateBuilder(store)
        builder.build(dry_run=False)
        # dry-run promote writes nothing
        pdry = builder.promote(dry_run=True)
        assert store.count_cross_source_relationships() == 0
        assert pdry["summary"]["promoted"] == 0
        assert pdry["summary"]["promotable"] >= 2  # the two deterministic procore edges
        # apply promote: only deterministic candidates land
        papply = builder.promote(dry_run=False)
        promoted = store.count_cross_source_relationships()
        assert promoted == papply["summary"]["promotable"]
        assert promoted >= 2
        # every promoted row is deterministic-promoted; none of the weak/strong/sensitive landed
        raw = sqlite3.connect(db)
        rows = raw.execute(
            "SELECT confidence_class, promoted_by, review_required FROM cross_source_relationships"
        ).fetchall()
        raw.close()
        assert all(r[0] == "deterministic" and r[1] == "deterministic" and r[2] == 0 for r in rows)
        # idempotent
        builder.promote(dry_run=False)
        assert store.count_cross_source_relationships() == promoted
    finally:
        Path(db).unlink(missing_ok=True)


def test_promote_no_raw_content() -> None:
    db = _fresh_db()
    try:
        _seed_procore_and_resolution(db)
        store = ConstructionStore(db_path=db)
        builder = CrossSourceRelationshipSubstrateBuilder(store)
        builder.build(dry_run=False)
        builder.promote(dry_run=False)
        raw = sqlite3.connect(db)
        blob = json.dumps(raw.execute("SELECT * FROM cross_source_relationships").fetchall())
        # guard columns all zero
        for row in raw.execute(f"SELECT {', '.join(_GUARDS)} FROM cross_source_relationships"):
            assert set(row) <= {0}
        raw.close()
        assert not _LEAK.search(blob)
    finally:
        Path(db).unlink(missing_ok=True)
