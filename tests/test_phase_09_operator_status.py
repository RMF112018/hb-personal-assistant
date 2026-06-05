"""Phase 09 Prompt 38 — CLI and operator status tests.

Covers the normal path, missing-policy fail-closed, stale-schema fail-closed, unsafe-source (missing
surface contract -> not overstated), the no-raw/no-writeback dashboard, and guard-clean artifacts.
"""

from __future__ import annotations

import json

import pytest

from hb_assistant.construction.second_brain import phase_09_operator_status as ops
from hb_assistant.store.migrator import SQLiteMigrator


def _migrated_db(tmp_path) -> str:
    db = str(tmp_path / "operator.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_normal_advisory_ready(tmp_path):
    report = ops.build_phase_09_operator_status(
        db_path=_migrated_db(tmp_path), evidence_dir=str(tmp_path / "ev"), write_evidence=False
    )

    assert report["overall_status"] == "advisory_ready"
    assert report["operator_status_ok"] is True
    assert report["schema_ready"] is True
    assert report["gates_ok"] is True
    assert report["all_contracts_present"] is True
    assert report["readiness_overstated"] is False
    assert report["surface_count"] >= 20
    assert report["makes_determination"] is False
    # repo-consistent: every surface carries a cli_path + kinds
    assert all(s.get("cli_path") and s.get("kinds") for s in report["surfaces"])


def test_missing_policy_fail_closed(monkeypatch):
    def _boom() -> dict:
        raise ops.Phase09OperatorStatusError("contract missing")

    monkeypatch.setattr(ops, "load_phase_09_operator_status_contract", _boom)
    with pytest.raises(ops.Phase09OperatorStatusError):
        ops.evaluate_phase_09_operator_status()


def test_stale_schema_fail_closed(tmp_path):
    import sqlite3

    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no schema_migrations
    with pytest.raises(ops.Phase09OperatorStatusError):
        ops.evaluate_phase_09_operator_status(db_path=empty)


def test_unsafe_source_missing_contract_not_overstated(tmp_path, monkeypatch):
    # a registry surface naming a missing contract must report contract_present=false (never overstated)
    from hb_assistant.construction.second_brain import contracts as contracts_mod

    real = contracts_mod.load_phase_09_contract

    def _patched(name: str):
        if name == "hybrid_retrieval_contract":
            return {}
        return real(name)

    monkeypatch.setattr(contracts_mod, "load_phase_09_contract", _patched)
    report = ops.evaluate_phase_09_operator_status(db_path=_migrated_db(tmp_path))

    assert "retrieval.hybrid" in report["missing_contracts"]
    assert report["all_contracts_present"] is False
    assert report["operator_status_ok"] is False
    assert report["overall_status"] != "advisory_ready"
    assert report["readiness_overstated"] is False  # honest: not overstated despite the gap


def test_no_raw_no_determination(tmp_path):
    report = ops.build_phase_09_operator_status(
        db_path=_migrated_db(tmp_path), evidence_dir=str(tmp_path / "ev"), write_evidence=False
    )
    assert report["read_only"] is True
    assert report["makes_determination"] is False
    serialized = json.dumps(report, default=str)
    for token in ("BEGIN", "PRIVATE KEY", "access_token", "client_secret"):
        assert token not in serialized


def test_writes_guard_clean_artifacts(tmp_path):
    out_dir = tmp_path / "evidence"
    report = ops.build_phase_09_operator_status(
        db_path=_migrated_db(tmp_path), evidence_dir=str(out_dir), write_evidence=True
    )

    json_path = out_dir / "phase-09-operator-status.json"
    md_path = out_dir / "phase-09-operator-status.md"
    assert json_path.exists() and md_path.exists()
    assert report["operator_status_ok"] is True

    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for token in ("BEGIN", "PRIVATE KEY", "access_token", "client_secret"):
        assert token not in text
