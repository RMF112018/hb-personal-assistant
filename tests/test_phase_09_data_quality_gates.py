"""Phase 09 Prompt 36 — Phase 09 data-quality gates tests.

Covers the normal path, missing-policy fail-closed, stale-schema fail-closed, unsafe-source
(missing surface contract -> fail-closed), the no-raw/no-writeback proof, and guard-clean artifacts.
"""

from __future__ import annotations

import json

import pytest

from hb_assistant.construction.second_brain import phase_09_gates as g
from hb_assistant.store.migrator import SQLiteMigrator


def _migrated_db(tmp_path) -> str:
    db = str(tmp_path / "operator.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_normal_clean_gates(tmp_path):
    report = g.build_phase_09_gates_proof(
        db_path=_migrated_db(tmp_path), evidence_dir=str(tmp_path / "ev"), write_evidence=False
    )

    assert report["ok"] is True
    assert report["proof_passed"] is True
    assert report["readiness_overstated"] is False
    assert report["gate_count"] >= 18
    assert report["status_counts"]["fail_blocking"] == 0
    assert report["required_fields_covered"] is True
    bs = report["by_field_status"]
    # structural + safety gates pass
    for name in (
        "phase_09_schema_present",
        "phase_09_guard_columns_clean",
        "no_raw_vector_content",
        "no_external_writeback_posture",
        "no_semantic_retrieval_bypass",
        "gates_contract_loaded",
        "lifecycle_contract_loaded",
    ):
        assert bs[name] == "pass"
    # an empty table-backed surface is honestly deferred
    assert bs["vector_index"] == "deferred_not_blocking"
    assert report["makes_determination"] is False


def test_missing_policy_fail_closed(monkeypatch):
    def _boom() -> dict:
        raise g.Phase09GatesError("contract missing")

    monkeypatch.setattr(g, "load_phase_09_gates_contract", _boom)
    with pytest.raises(g.Phase09GatesError):
        g.evaluate_phase_09_data_quality_gates()


def test_stale_schema_fail_closed(tmp_path):
    import sqlite3

    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no schema_migrations / no tables
    report = g.evaluate_phase_09_data_quality_gates(db_path=empty)

    assert report["ok"] is False
    assert report["by_field_status"]["phase_09_schema_present"] == "fail_blocking"


def test_unsafe_source_missing_contract_fail_closed(tmp_path, monkeypatch):
    # a surface whose contract is missing must fail closed (fail_blocking), never silently pass
    from hb_assistant.construction.second_brain import contracts as contracts_mod

    real = contracts_mod.load_phase_09_contract

    def _patched(name: str):
        if name == "hallucination_risk_checks_contract":
            return {}
        return real(name)

    monkeypatch.setattr(contracts_mod, "load_phase_09_contract", _patched)
    report = g.evaluate_phase_09_data_quality_gates(db_path=_migrated_db(tmp_path))

    assert report["by_field_status"]["hallucination_risk_checks"] == "fail_blocking"
    assert report["ok"] is False
    # no raw value leaked — the gate carries only the contract name + reason
    serialized = json.dumps(report["gates"], default=str)
    assert "CONTRACT_MISSING" in serialized


def test_no_raw_no_writeback_proof_clean(tmp_path):
    report = g.build_phase_09_gates_proof(
        db_path=_migrated_db(tmp_path), evidence_dir=str(tmp_path / "ev"), write_evidence=False
    )
    assert report["proof_passed"] is True
    bs = report["by_field_status"]
    assert bs["no_external_writeback_posture"] == "pass"
    assert bs["no_semantic_retrieval_bypass"] == "pass"
    serialized = json.dumps(report, default=str)
    for token in ("BEGIN", "PRIVATE KEY", "access_token", "client_secret"):
        assert token not in serialized


def test_proof_writes_guard_clean_artifacts(tmp_path):
    out_dir = tmp_path / "evidence"
    report = g.build_phase_09_gates_proof(
        db_path=_migrated_db(tmp_path), evidence_dir=str(out_dir), write_evidence=True
    )

    json_path = out_dir / "phase-09-gates-proof.json"
    md_path = out_dir / "phase-09-gates-proof.md"
    assert json_path.exists() and md_path.exists()
    assert report["proof_passed"] is True

    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for token in ("BEGIN", "PRIVATE KEY", "access_token", "client_secret"):
        assert token not in text
