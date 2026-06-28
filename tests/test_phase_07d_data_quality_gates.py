"""Phase 07D Prompt 12 — 07D data-quality gates (full 12-field conformance + safe counts)."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from hb_assistant.construction.config.models import SourceLocation, SourceRegistry
from hb_assistant.construction.data_quality import (
    build_table_inventory_report,
    evaluate_data_quality_gates,
    evaluate_phase_07d_data_quality_gates,
)
from hb_assistant.construction.policy.document_source_policy import DocumentSourcePolicy
from hb_assistant.construction.relationships.contracts import load_phase_07d_contract
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}",
    re.IGNORECASE,
)
_CONTRACT_FIELDS = set(load_phase_07d_contract("phase_07d_data_quality_gates")["required_fields"])


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_p07dgates_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _seed_full(store: ConstructionStore) -> None:
    store.upsert_cross_source_relationship_candidate(
        candidate_id="c0",
        source_family="email",
        source_record_type="m",
        source_record_ref="m0",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="r0",
        relationship_type="references",
        confidence_score=1.0,
        confidence_class="deterministic",
        source_reference_json="{}",
        deterministic=True,
        review_required=False,
        project_key="tropical",
        evidence_trail_id="et0",
    )
    store.upsert_source_evidence_trail(
        evidence_trail_id="et0",
        evidence_kind="x",
        source_refs_json="{}",
        confidence_class="deterministic",
        project_key="tropical",
    )
    store.upsert_meeting_prep_brief_run(
        brief_run_id="b0",
        project_key="tropical",
        mode="apply",
        lookahead_days=7,
        status="materialized",
        sections_written=8,
    )
    store.upsert_project_issue_history_item(
        issue_family_id="i0",
        project_key="tropical",
        status="open",
        source_families_json="[]",
        confidence_class="deterministic",
        stale_unknown_flags_json=json.dumps({"x": 1}),
    )
    store.upsert_project_risk_digest_item(
        risk_digest_id="r0",
        project_key="tropical",
        risk_indicator_type="x",
        risk_source_class="source_stated",
        summary_redacted="{}",
        confidence_class="deterministic",
    )
    store.upsert_aging_exposure_report_item(
        aging_item_id="a0",
        project_key="tropical",
        record_family="rfis",
        record_ref="k",
        status="open",
        threshold_band="unknown",
        missing_status_flag=True,
    )
    store.upsert_cross_source_intelligence_obsidian_run(
        obsidian_run_id="o0",
        mode="dry_run",
        output_kind="x",
        status="rendered",
        notes_written=0,
    )


def _src(key: str, kind: str, **kw: object) -> SourceLocation:
    return SourceLocation(source_key=key, kind=kind, display_name=key, **kw)


# ---------------------------------------------------------------------------


def test_full_twelve_field_report() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_full(store)
        report = evaluate_phase_07d_data_quality_gates(db_path=db)
        assert report["ok"] is True
        assert set(report["by_field_status"].keys()) == _CONTRACT_FIELDS
        assert report["required_fields_covered"] is True
        for field in (
            "meeting_prep_brief_generation_coverage",
            "issue_history_coverage",
            "risk_digest_coverage",
            "aging_report_coverage",
            "obsidian_output_safety",
            "stale_unknown_warning_coverage",
        ):
            assert report["by_field_status"][field] == "pass"
        assert report["phase_07d_intelligence_ready"] is True
    finally:
        Path(db).unlink(missing_ok=True)


def test_empty_db_defers_coverage_never_overstated() -> None:
    db = _fresh_db()
    try:
        report = evaluate_phase_07d_data_quality_gates(db_path=db)
        assert report["ok"] is True
        for field in (
            "meeting_prep_brief_generation_coverage",
            "issue_history_coverage",
            "risk_digest_coverage",
            "aging_report_coverage",
            "stale_unknown_warning_coverage",
            "obsidian_output_safety",
        ):
            assert report["by_field_status"][field] == "deferred_not_blocking"
        assert report["phase_07d_intelligence_ready"] is False
        # the no-writeback proof still passes over an empty (clean) DB
        assert report["by_field_status"]["no_writeback_no_secret_no_raw_content_proof"] == "pass"
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_writeback_proof_clean_and_no_raw() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_full(store)
        report = evaluate_phase_07d_data_quality_gates(db_path=db)
        proof = report["no_writeback_proof"]
        assert proof["proof_passed"] is True
        assert proof["guard_violations"] == 0
        assert proof["pattern_hits"] == 0
        assert proof["tables_scanned"] == 10
        assert _LEAK.search(json.dumps(report, default=str)) is None
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_required_total_surfaced() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        # a sensitive candidate routed to review -> a review item is recorded
        store.upsert_cross_source_relationship_candidate(
            candidate_id="c1",
            source_family="email",
            source_record_type="m",
            source_record_ref="m1",
            target_family="procore",
            target_record_type="rfi",
            target_record_ref="r1",
            relationship_type="claim_notice",
            confidence_score=0.5,
            confidence_class="weak_heuristic",
            source_reference_json="{}",
            sensitive_high_impact=True,
            review_required=False,
            project_key="tropical",
            evidence_trail_id="et1",
        )
        report = evaluate_phase_07d_data_quality_gates(db_path=db)
        # the misrouted sensitive candidate makes the routing gate fail and adds a review item
        assert (
            report["by_field_status"]["weak_model_sensitive_review_routing_accuracy"]
            == "fail_blocking"
        )
        assert report["review_required_total"] >= 1
        assert report["ok"] is False
    finally:
        Path(db).unlink(missing_ok=True)


def test_source_scope_safe_counts(monkeypatch) -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        # need a document card so the source-scope gate is not deferred
        store.upsert_document_card(card_id="card1", source_id="sp", project_key="alpha")
        registry = SourceRegistry(
            sources=[
                _src("sp_nested", "sharepoint_project_drive_folder", folder_item_id="F"),
                _src("od_subset", "onedrive_business_root", selected_folder_item_ids=["f1"]),
                _src("od_all", "onedrive_business_root", allow_all_folders=True),
                _src("od_implicit", "onedrive_business_root"),  # implicit root -> blocked
            ]
        )
        monkeypatch.setattr(
            "hb_assistant.construction.config.load_source_registry", lambda: registry
        )
        monkeypatch.setattr(
            "hb_assistant.construction.policy.document_source_policy.load_document_source_policy",
            lambda: DocumentSourcePolicy(),
        )
        report = evaluate_phase_07d_data_quality_gates(db_path=db)
        counts = report["source_scope_safe_counts"]
        assert counts["onedrive_explicit_subset_sources"] == 1
        assert (
            counts["onedrive_explicit_all_folders_sources"] == 1
        )  # explicit -> compliant, not blocked
        assert counts["onedrive_implicit_root_blocked_sources"] == 1
        assert counts["sharepoint_approved_all_nested_sources"] == 1
        # no raw folder names / paths / urls / ids in the output
        assert "folder_item_id" not in json.dumps(report)
        assert _LEAK.search(json.dumps(report, default=str)) is None
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_full(store)
        r1 = evaluate_phase_07d_data_quality_gates(db_path=db)
        r2 = evaluate_phase_07d_data_quality_gates(db_path=db)
        assert r1["by_field_status"] == r2["by_field_status"]
        assert r1["no_writeback_proof"] == r2["no_writeback_proof"]
    finally:
        Path(db).unlink(missing_ok=True)


def test_gates_command_carries_safe_counts() -> None:
    db = _fresh_db()
    try:
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        gate = next(
            g for g in report["gates"] if g["gate_name"] == "meeting_prep_prerequisite_status"
        )
        sc = gate.get("source_scope_safe_counts")
        # may be None when registry/policy unavailable in the test env; if present, the four keys
        if sc is not None:
            assert set(sc.keys()) == {
                "onedrive_explicit_subset_sources",
                "onedrive_explicit_all_folders_sources",
                "onedrive_implicit_root_blocked_sources",
                "sharepoint_approved_all_nested_sources",
            }
    finally:
        Path(db).unlink(missing_ok=True)


def test_table_inventory_unchanged() -> None:
    assert build_table_inventory_report()["contract_table_count"] == 475  # live table lifecycle contract count (was 439; 451 before V76 staffing)
