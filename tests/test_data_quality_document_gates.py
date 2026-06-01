"""Phase 07C Prompt 11 — 07C document-intelligence data-quality gates."""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

from hb_assistant.construction.data_quality import evaluate_data_quality_gates
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_NEW_07C_GATES = (
    "document_classification_coverage",
    "document_project_match_coverage",
    "document_extraction_eligibility_status",
    "document_relationship_population_status",
    "document_source_scope_compliance",
    "document_intelligence_safety_scan",
)
_WHITELIST = {"pass", "warning", "fail_blocking", "deferred_not_blocking", "not_applicable"}


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_07c_gates_")
    import os

    os.close(fd)
    with contextlib.suppress(Exception):
        SQLiteMigrator(db_path=db).apply()
    return db


def _status_map(report: dict) -> dict:
    return {g["gate_name"]: g["gate_status"] for g in report["gates"]}


def _phase_map(report: dict) -> dict:
    return {g["gate_name"]: g.get("future_phase") for g in report["gates"]}


def _seed_card(store: ConstructionStore, *, key: str, classified: bool = True) -> None:
    store.upsert_inventory_item(
        source_key="sp", drive_id="d", item_id=key, name="raw_" + key, web_url="https://x/" + key,
        parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
    )
    store.upsert_document_card(
        card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
        file_extension="pdf", project_key="alpha", document_type="unknown", size_class="small",
        extraction_eligibility="manual_approval_required", review_required=True,
    )
    store.upsert_document_project_match_candidate(
        candidate_id="pm_" + key, document_card_id=key, project_key="alpha",
        candidate_type="deterministic", confidence=0.95, confidence_class="deterministic",
        deterministic=True, review_required=False,
    )
    if classified:
        store.upsert_document_classification_candidate(
            candidate_id="clf_" + key, document_card_id=key, document_type="rfi",
            classifier_name="deterministic_v1", signal_class="deterministic", confidence=0.9,
            confidence_class="deterministic",
        )


def test_full_07c_chain_passes_new_gates() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db)
        _seed_card(store, key="c0")
        store.upsert_document_relationship_candidate(
            candidate_id="rel_c0", document_card_id="c0", target_system="procore",
            target_record_type="rfi", target_record_key_hash="hh", relationship_type="x",
            candidate_type="heuristic", confidence=0.55, confidence_class="moderate_heuristic",
            review_required=True,
        )
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        statuses = _status_map(report)
        phases = _phase_map(report)

        for gate in _NEW_07C_GATES:
            assert gate in statuses, gate
            assert phases[gate] == "07C", (gate, phases[gate])
            assert statuses[gate] in _WHITELIST, (gate, statuses[gate])

        # Data-presence + safety gates pass on a complete, clean chain.
        assert statuses["document_classification_coverage"] == "pass"
        assert statuses["document_project_match_coverage"] == "pass"
        assert statuses["document_extraction_eligibility_status"] == "pass"
        assert statuses["document_relationship_population_status"] == "pass"
        assert statuses["document_intelligence_safety_scan"] == "pass"

        assert len(report["gates"]) >= 18
        assert report["meeting_prep_readiness_claim"] != "ready"
    finally:
        Path(db).unlink(missing_ok=True)


def test_missing_classification_defers_and_blocks_readiness() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db)
        _seed_card(store, key="c0", classified=False)  # card but no classification candidate
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        statuses = _status_map(report)

        assert statuses["document_classification_coverage"] == "deferred_not_blocking"
        prep = report["phase_go_nogo"]["07D"]["meeting_prep_readiness"]
        assert prep["ready"] is False
        assert "document_classification_coverage" in prep["blocked_by"]
        # Every gate status stays within the allowed vocabulary.
        for g in report["gates"]:
            assert g["gate_status"] in _WHITELIST, (g["gate_name"], g["gate_status"])
    finally:
        Path(db).unlink(missing_ok=True)


def _gate(report: dict, name: str) -> dict:
    return next(g for g in report["gates"] if g["gate_name"] == name)


def test_review_routing_passes_on_document_review_queue() -> None:
    """Phase 07D — review-routing reconciles across queues: a review-required document
    card alone proves the routing path exists (relationship queue may be empty)."""
    db = _fresh_db()
    try:
        store = ConstructionStore(db)
        _seed_card(store, key="c0")  # review_required=True document card
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        gate = _gate(report, "review_required_routing_presence")
        assert gate["gate_status"] == "pass"
        breakdown = gate["review_routing_breakdown"]
        assert breakdown["construction_document_cards"] >= 1
        assert breakdown["relationship_resolution_queue"] == 0  # empty, yet gate passes
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_routing_defers_on_empty_queues() -> None:
    db = _fresh_db()
    try:
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        gate = _gate(report, "review_required_routing_presence")
        assert gate["gate_status"] == "deferred_not_blocking"
        assert all(v == 0 for v in gate["review_routing_breakdown"].values())
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_routing_is_idempotent() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db)
        _seed_card(store, key="c0")
        r1 = _gate(evaluate_data_quality_gates(db_path=db, persist=False), "review_required_routing_presence")
        r2 = _gate(evaluate_data_quality_gates(db_path=db, persist=False), "review_required_routing_presence")
        assert r1["gate_status"] == r2["gate_status"] == "pass"
        assert r1["review_routing_breakdown"] == r2["review_routing_breakdown"]
    finally:
        Path(db).unlink(missing_ok=True)


def test_source_scope_gate_surfaces_onedrive_breakdown() -> None:
    """The document_source_scope_compliance gate attaches the explicit-compliant vs
    implicit-blocked OneDrive distinction (driven by the live registry/policy)."""
    db = _fresh_db()
    try:
        gate = _gate(
            evaluate_data_quality_gates(db_path=db, persist=False),
            "document_source_scope_compliance",
        )
        breakdown = gate["onedrive_scope_breakdown"]
        # Keys are always present; values are non-negative ints from the registry.
        assert set(breakdown) == {
            "all_folders_explicit_compliant",
            "selected_folders_compliant",
            "implicit_root_blocked",
        }
        assert all(isinstance(v, int) and v >= 0 for v in breakdown.values())
    finally:
        Path(db).unlink(missing_ok=True)


def test_empty_store_defers_07c_gates() -> None:
    db = _fresh_db()
    try:
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        statuses = _status_map(report)
        # Data-presence gates defer on an empty store (missing 07C data blocks readiness).
        assert statuses["document_classification_coverage"] == "deferred_not_blocking"
        assert statuses["document_project_match_coverage"] == "deferred_not_blocking"
        assert statuses["document_extraction_eligibility_status"] == "deferred_not_blocking"
        assert statuses["document_relationship_population_status"] == "deferred_not_blocking"
        # Safety scan is vacuously clean on empty tables.
        assert statuses["document_intelligence_safety_scan"] == "pass"
        assert report["meeting_prep_readiness_claim"] != "ready"
    finally:
        Path(db).unlink(missing_ok=True)
