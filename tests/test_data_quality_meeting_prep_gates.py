"""Phase 07D Prompt 05 — meeting-prep prerequisite gates over the V25 substrate.

Covers: gate presence + phase tagging, success path, blocked path (missing evidence
trails), review-required routing, the source-scope 3-way (pass / fail_blocking /
deferred_not_blocking), no-raw-content, idempotency, the prereq-constant ⊆ contract
invariant, and backward-compatible meeting_prep_readiness keys.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from hb_assistant.construction.config.models import SourceLocation, SourceRegistry
from hb_assistant.construction.data_quality import evaluate_data_quality_gates
from hb_assistant.construction.data_quality.gates import _MEETING_PREP_07D_PREREQUISITES
from hb_assistant.construction.policy.document_source_policy import (
    DocumentSourcePolicy,
    OneDriveScopePolicy,
)
from hb_assistant.construction.relationships.contracts import load_phase_07d_contract
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_WHITELIST = {"pass", "warning", "fail_blocking", "deferred_not_blocking", "not_applicable"}
_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}", re.IGNORECASE
)
_NEW_GATES = list(_MEETING_PREP_07D_PREREQUISITES)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_mprep_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _status_map(report: dict) -> dict:
    return {g["gate_name"]: g["gate_status"] for g in report["gates"]}


def _gate(report: dict, name: str) -> dict:
    return next(g for g in report["gates"] if g["gate_name"] == name)


def _cand(store: ConstructionStore, cid: str, **over: object) -> None:
    kw: dict = {
        "candidate_id": cid,
        "source_family": "document",
        "source_record_type": "document_card",
        "source_record_ref": "card:" + cid,
        "target_family": "procore",
        "target_record_type": "procore_rfi",
        "target_record_ref": "rfi:" + cid,
        "relationship_type": "references",
        "confidence_score": 1.0,
        "confidence_class": "deterministic",
        "source_reference_json": json.dumps({"src": cid, "tgt": "rfi:" + cid}),
        "deterministic": True,
        "model_proposed": False,
        "sensitive_high_impact": False,
        "review_required": False,
    }
    kw.update(over)
    store.upsert_cross_source_relationship_candidate(**kw)  # type: ignore[arg-type]


def _trail(store: ConstructionStore, cid: str) -> None:
    store.upsert_source_evidence_trail(
        evidence_trail_id="et_" + cid,
        evidence_kind="cross_source_relationship",
        source_refs_json=json.dumps({"refs": ["card:" + cid, "rfi:" + cid]}),
        confidence_class="deterministic",
        relationship_candidate_id=cid,
    )


# ---------------------------------------------------------------------------
# Presence + phase tagging
# ---------------------------------------------------------------------------


def test_new_07d_gates_present_phased_and_deferred_when_empty() -> None:
    db = _fresh_db()
    try:
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        statuses = _status_map(report)
        for name in _NEW_GATES:
            g = _gate(report, name)
            assert g["future_phase"] == "07D"
            assert g["gate_status"] in _WHITELIST
            # empty substrate is never a pass and never a hard block
            assert g["gate_status"] == "deferred_not_blocking"
        assert report["meeting_prep_readiness_claim"] != "ready"
        # all five 07D prereqs land in the readiness blocked_by set
        blocked = set(report["phase_go_nogo"]["07D"]["meeting_prep_readiness"]["blocked_by"])
        assert set(_NEW_GATES) <= blocked
        assert all(statuses[n] in _WHITELIST for n in _NEW_GATES)
    finally:
        Path(db).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Relationship substrate success / blocked
# ---------------------------------------------------------------------------


def test_relationship_substrate_success_path() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        for i in range(3):
            cid = f"c{i}"
            _cand(store, cid, evidence_trail_id="et_" + cid)
            _trail(store, cid)
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        statuses = _status_map(report)
        assert statuses["cross_source_relationship_candidate_coverage"] == "pass"
        assert statuses["deterministic_relationship_quality"] == "pass"
        assert statuses["evidence_trail_completeness"] == "pass"
        assert statuses["weak_model_sensitive_review_routing_accuracy"] == "deferred_not_blocking"
        cats = report["phase_go_nogo"]["07D"]["meeting_prep_readiness"]["prerequisite_categories"]
        assert cats["relationship"]["ready"] is True
        assert cats["relationship"]["blocked_by"] == []
    finally:
        Path(db).unlink(missing_ok=True)


def test_missing_evidence_trails_is_fail_blocking() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0")  # candidate but no evidence trail
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "evidence_trail_completeness")
        assert g["gate_status"] == "fail_blocking"
        assert g["blocking"] == 1
        assert g["reason"] == "missing_evidence_trails"
        blocked = report["phase_go_nogo"]["07D"]["meeting_prep_readiness"]["blocked_by"]
        assert "evidence_trail_completeness" in blocked
    finally:
        Path(db).unlink(missing_ok=True)


def test_malformed_deterministic_edge_is_fail_blocking() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        # deterministic flag but flagged sensitive_high_impact -> malformed
        _cand(store, "c0", sensitive_high_impact=True, review_required=True, evidence_trail_id="et_c0")
        _trail(store, "c0")
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "deterministic_relationship_quality")
        assert g["gate_status"] == "fail_blocking"
        assert g["malformed_count"] == 1
    finally:
        Path(db).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Review-required routing (review + safety)
# ---------------------------------------------------------------------------


def test_review_routing_pass_when_sensitive_is_routed() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(
            store, "c0", deterministic=False, model_proposed=True,
            confidence_class="model_proposed", review_required=True, evidence_trail_id="et_c0",
        )
        _trail(store, "c0")
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "weak_model_sensitive_review_routing_accuracy")
        assert g["gate_status"] == "pass"
        assert g["misrouted_count"] == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_routing_fail_when_sensitive_not_routed() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(
            store, "c0", deterministic=False, sensitive_high_impact=True,
            confidence_class="weak_heuristic", review_required=False, evidence_trail_id="et_c0",
        )
        _trail(store, "c0")
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "weak_model_sensitive_review_routing_accuracy")
        assert g["gate_status"] == "fail_blocking"
        assert g["misrouted_count"] == 1
        assert report["review_items"]
    finally:
        Path(db).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Source-scope 3-way (pass / fail_blocking / deferred_not_blocking)
# ---------------------------------------------------------------------------


def _src(source_key: str, kind: str, **kw: object) -> SourceLocation:
    return SourceLocation(source_key=source_key, kind=kind, display_name=source_key, **kw)


def _patch_scope(monkeypatch, registry: SourceRegistry, policy: DocumentSourcePolicy) -> None:
    monkeypatch.setattr(
        "hb_assistant.construction.config.load_source_registry", lambda: registry
    )
    monkeypatch.setattr(
        "hb_assistant.construction.policy.document_source_policy.load_document_source_policy",
        lambda: policy,
    )


def _seed_card(store: ConstructionStore) -> None:
    store.upsert_document_card(card_id="card1", source_id="sp", project_key="alpha")


def test_source_scope_pass_explicit_all_folders(monkeypatch) -> None:
    db = _fresh_db()
    try:
        _seed_card(ConstructionStore(db_path=db))
        registry = SourceRegistry(
            sources=[
                _src("sp_nested", "sharepoint_project_drive_folder", folder_item_id="F"),
                _src("od_all", "onedrive_business_root", allow_all_folders=True),
            ]
        )
        _patch_scope(monkeypatch, registry, DocumentSourcePolicy())
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "meeting_prep_prerequisite_status")
        assert g["gate_status"] == "pass"
        assert g["onedrive_scope_breakdown"]["all_folders_explicit_compliant"] >= 1
        assert g["onedrive_scope_breakdown"]["implicit_root_blocked"] == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_source_scope_fail_blocking_implicit_root(monkeypatch) -> None:
    db = _fresh_db()
    try:
        _seed_card(ConstructionStore(db_path=db))
        registry = SourceRegistry(
            sources=[_src("od_implicit", "onedrive_business_root")]  # no allowlist -> blocked
        )
        _patch_scope(monkeypatch, registry, DocumentSourcePolicy())
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "meeting_prep_prerequisite_status")
        assert g["gate_status"] == "fail_blocking"
        assert g["blocking"] == 1
        assert g["blocked_sources"] == ["od_implicit"]
    finally:
        Path(db).unlink(missing_ok=True)


def test_source_scope_deferred_when_no_onedrive(monkeypatch) -> None:
    db = _fresh_db()
    try:
        _seed_card(ConstructionStore(db_path=db))
        registry = SourceRegistry(
            sources=[_src("sp_only", "sharepoint_project_drive_folder", folder_item_id="F")]
        )
        _patch_scope(monkeypatch, registry, DocumentSourcePolicy())
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "meeting_prep_prerequisite_status")
        assert g["gate_status"] == "deferred_not_blocking"
        assert g["reason"] == "no_onedrive_sources_or_no_document_cards"
    finally:
        Path(db).unlink(missing_ok=True)


def test_source_scope_deferred_when_no_document_cards(monkeypatch) -> None:
    db = _fresh_db()
    try:
        # OneDrive source present and compliant, but zero document-card inputs.
        registry = SourceRegistry(
            sources=[_src("od_all", "onedrive_business_root", allow_all_folders=True)]
        )
        _patch_scope(monkeypatch, registry, DocumentSourcePolicy())
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "meeting_prep_prerequisite_status")
        assert g["gate_status"] == "deferred_not_blocking"
        assert g["document_card_count"] == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_source_scope_not_blocked_solely_by_explicit_all_folders_disabled_capability(
    monkeypatch,
) -> None:
    """When the policy disables the explicit all-folders capability, an all-folders source
    becomes implicit-root-blocked -> fail_blocking (proving the gate keys off real
    compliance, not merely the presence of an all-folders opt-in)."""
    db = _fresh_db()
    try:
        _seed_card(ConstructionStore(db_path=db))
        registry = SourceRegistry(
            sources=[_src("od_all", "onedrive_business_root", allow_all_folders=True)]
        )
        policy = DocumentSourcePolicy(
            onedrive=OneDriveScopePolicy(allow_explicit_all_folders=False)
        )
        _patch_scope(monkeypatch, registry, policy)
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        g = _gate(report, "meeting_prep_prerequisite_status")
        assert g["gate_status"] == "fail_blocking"
    finally:
        Path(db).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Safety / idempotency / contract / backward-compat
# ---------------------------------------------------------------------------


def test_no_raw_content_in_report() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        for i in range(2):
            cid = f"c{i}"
            _cand(store, cid, evidence_trail_id="et_" + cid)
            _trail(store, cid)
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        # the source_reference_json/signals_json blobs must not surface in the report
        assert _LEAK.search(json.dumps(report, default=str)) is None
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent_persisted_runs() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", evidence_trail_id="et_c0")
        _trail(store, "c0")
        r1 = evaluate_data_quality_gates(db_path=db, persist=True)
        r2 = evaluate_data_quality_gates(db_path=db, persist=True)
        s1 = _status_map(r1)
        s2 = _status_map(r2)
        for name in _NEW_GATES:
            assert s1[name] == s2[name]
            assert s1[name] in _WHITELIST
    finally:
        Path(db).unlink(missing_ok=True)


def test_prereq_constant_subset_of_contract() -> None:
    contract = load_phase_07d_contract("phase_07d_data_quality_gates")
    required = set(contract["required_fields"])
    assert set(_MEETING_PREP_07D_PREREQUISITES) <= required


def test_meeting_prep_readiness_backward_compatible_keys() -> None:
    db = _fresh_db()
    try:
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        prep = report["phase_go_nogo"]["07D"]["meeting_prep_readiness"]
        for key in ("ready", "blocked_by", "prerequisites", "auto_readiness_allowed"):
            assert key in prep
        assert prep["auto_readiness_allowed"] is False
        cats = prep["prerequisite_categories"]
        assert set(cats.keys()) == {
            "calendar", "email", "document", "relationship", "review", "safety", "source_scope"
        }
    finally:
        Path(db).unlink(missing_ok=True)
