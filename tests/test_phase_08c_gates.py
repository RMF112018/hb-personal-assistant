"""Phase 08C — data-quality gate evaluator + evidence proof.

Covers the four-status taxonomy classification (pass / warning / fail_blocking /
deferred_not_blocking), readiness_overstated computation, the written
phase-08c-gates-proof.json, and the stop condition: gates must NOT pass when
required evidence (tables / contracts / guard columns) is missing.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain import data_quality as dq
from hb_assistant.store.migrator import SQLiteMigrator

_FC = "hb_assistant.construction.second_brain.financial_completeness"
_AN = "hb_assistant.construction.second_brain.financial_amount_normalization"
_NW = "hb_assistant.construction.second_brain.financial_no_writeback"


# --------------------------------------------------------------------------- helpers


def test_count_gate_statuses_covers_four_classifications() -> None:
    gates = [
        {"gate_name": "a", "gate_status": "pass"},
        {"gate_name": "b", "gate_status": "pass"},
        {"gate_name": "c", "gate_status": "warning"},
        {"gate_name": "d", "gate_status": "fail_blocking"},
        {"gate_name": "e", "gate_status": "deferred_not_blocking"},
        {"gate_name": "f", "gate_status": "unknown_status"},  # ignored
    ]
    counts = dq._count_gate_statuses(gates)
    assert counts == {
        "pass": 2,
        "warning": 1,
        "fail_blocking": 1,
        "deferred_not_blocking": 1,
    }


def test_readiness_overstated_false_when_no_fail() -> None:
    gates = [
        {"gate_name": "readiness_agent", "gate_status": "pass"},
        {"gate_name": "forecast_readiness", "gate_status": "warning"},
        {"gate_name": "second_brain_financial_amount_facts_normalized", "gate_status": "pass"},
    ]
    assert dq._compute_readiness_overstated(gates) is False


def test_readiness_overstated_true_when_readiness_passes_with_fail() -> None:
    gates = [
        {"gate_name": "readiness_agent", "gate_status": "pass"},
        {
            "gate_name": "second_brain_financial_amount_facts_normalized",
            "gate_status": "fail_blocking",
        },
    ]
    assert dq._compute_readiness_overstated(gates) is True


def test_readiness_not_overstated_when_readiness_not_passing() -> None:
    gates = [
        {"gate_name": "readiness_agent", "gate_status": "warning"},
        {"gate_name": "forecast_readiness", "gate_status": "fail_blocking"},
        {"gate_name": "review_required_policy", "gate_status": "warning"},
    ]
    assert dq._compute_readiness_overstated(gates) is False


def test_missing_required_evidence_selects_schema_reasons() -> None:
    gates = [
        {"gate_name": "t1", "gate_status": "fail_blocking", "reason": "TABLE_ABSENT_IN_V35"},
        {"gate_name": "t2", "gate_status": "fail_blocking", "reason": "GUARD_COLUMN_MISSING"},
        {
            "gate_name": "schema_contracts",
            "gate_status": "fail_blocking",
            "reason": "CONTRACT_LOAD_FAILED: x",
        },
        {"gate_name": "other", "gate_status": "fail_blocking", "reason": "SOMETHING_ELSE"},
        {"gate_name": "ok", "gate_status": "pass"},
    ]
    missing = dq._missing_required_evidence(gates)
    assert "t1" in missing and "t2" in missing and "schema_contracts" in missing
    assert "other" not in missing and "ok" not in missing


# --------------------------------------------------------------------------- proof writer

_CLEAN_REPORT = {
    "ok": True,
    "schema_version": 36,
    "schema_version_expected": 35,
    "contract_version": "phase_08c_data_quality_gates-v1",
    "gates": [
        {"gate_name": "schema_contracts", "gate_status": "pass"},
        {"gate_name": "readiness_agent", "gate_status": "pass"},
    ],
    "by_field_status": {"schema_contracts": "pass", "readiness_agent": "pass"},
    "status_counts": {"pass": 2, "warning": 0, "fail_blocking": 0, "deferred_not_blocking": 0},
    "required_fields_covered": True,
    "readiness_overstated": False,
    "guardrails": {"advisory_only": True, "no_external_writeback": True},
}


def test_proof_written_and_passes_on_clean_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        dq, "evaluate_phase_08c_data_quality_gates", lambda **k: dict(_CLEAN_REPORT)
    )
    proof = dq.build_phase_08c_gates_proof(out_dir=str(tmp_path))

    assert proof["proof_passed"] is True
    assert proof["missing_required_evidence"] == []
    assert proof["stop_checks"]["gates_passed_with_missing_evidence"] is False

    json_path = tmp_path / "phase-08c-gates-proof.json"
    md_path = tmp_path / "phase-08c-gates-proof.md"
    assert json_path.exists() and md_path.exists()
    written = json.loads(json_path.read_text())
    assert written["proof_passed"] is True
    assert written["readiness_overstated"] is False
    assert "Phase 08C Data-Quality Gates Proof" in md_path.read_text()


def test_proof_fails_when_required_evidence_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = dict(_CLEAN_REPORT)
    report["ok"] = False
    report["gates"] = [
        {
            "gate_name": "second_brain_financial_amount_facts_normalized",
            "gate_status": "fail_blocking",
            "reason": "TABLE_ABSENT_IN_V35",
        },
    ]
    report["by_field_status"] = {"second_brain_financial_amount_facts_normalized": "fail_blocking"}
    report["status_counts"] = {
        "pass": 0,
        "warning": 0,
        "fail_blocking": 1,
        "deferred_not_blocking": 0,
    }
    monkeypatch.setattr(dq, "evaluate_phase_08c_data_quality_gates", lambda **k: report)

    proof = dq.build_phase_08c_gates_proof(out_dir=str(tmp_path))

    # stop condition: gates do NOT pass when required evidence is missing
    assert proof["proof_passed"] is False
    assert "second_brain_financial_amount_facts_normalized" in proof["missing_required_evidence"]
    assert proof["stop_checks"]["gates_passed_with_missing_evidence"] is False
    written = json.loads((tmp_path / "phase-08c-gates-proof.json").read_text())
    assert written["proof_passed"] is False


# --------------------------------------------------------------------------- orchestration smoke


def _stub_heavy_builders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        f"{_AN}.run_amount_normalization",
        lambda *a, **k: {"run_id": "a", "stats": {}, "fields_discovered": []},
    )
    monkeypatch.setattr(
        f"{_FC}.run_financial_completeness",
        lambda *a, **k: {
            "currency": {"stats": {}},
            "wbs": {"present": {}, "missing": {}, "review_required_count": 0},
            "source": {"families": []},
        },
    )
    monkeypatch.setattr(
        f"{_FC}.build_financial_source_coverage_matrix", lambda *a, **k: {"summary": {}}
    )
    monkeypatch.setattr(
        f"{_FC}.build_financial_exposure_mart_preview",
        lambda *a, **k: {
            "summary": {},
            "items": [
                {"advisory_status": "advisory review aid only — not a final exposure determination"}
            ],
        },
    )
    monkeypatch.setattr(
        f"{_FC}.run_financial_fact_readiness_agent",
        lambda *a, **k: {"status": "succeeded", "run_id": "r", "items_evaluated": 0},
    )
    monkeypatch.setattr(
        dq,
        "evaluate_forecast_readiness_gates",
        lambda *a, **k: {
            "gate_status": "pass",
            "readiness_status": "ready_with_review_required",
            "summary": {"context_items_count": 0, "review_items_count": 0},
            "proof_path": "p",
            "md_path": "m",
        },
    )
    monkeypatch.setattr(
        f"{_NW}.run_financial_no_writeback_checks",
        lambda *a, **k: {
            "guard_columns": {"passed": True},
            "money_not_float": {"passed": True},
            "evidence_redaction": {"passed": True},
            "no_live_no_writeback": {"passed": True},
        },
    )


def test_evaluator_clean_on_migrated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "gates.db"
    SQLiteMigrator(db_path=str(db)).apply()
    _stub_heavy_builders(monkeypatch)

    report = dq.evaluate_phase_08c_data_quality_gates(db_path=str(db))

    assert set(report["status_counts"]) == {
        "pass",
        "warning",
        "fail_blocking",
        "deferred_not_blocking",
    }
    assert report["ok"] is True
    assert report["status_counts"]["fail_blocking"] == 0
    assert report["readiness_overstated"] is False
    # the ten V35 tables + structural gates are all present and passing
    assert report["by_field_status"]["second_brain_financial_amount_facts_normalized"] == "pass"
    assert report["by_field_status"]["no_writeback_no_raw_financial_output"] == "pass"


def test_evaluator_fails_on_unmigrated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "empty.db"
    sqlite3.connect(str(db)).close()  # exists but no V35 tables
    _stub_heavy_builders(monkeypatch)

    report = dq.evaluate_phase_08c_data_quality_gates(db_path=str(db))

    assert report["ok"] is False
    assert report["status_counts"]["fail_blocking"] >= 10  # the ten absent V35 tables
    assert dq._missing_required_evidence(report["gates"])
    # readiness claimed while required tables absent → overstated signal fires
    assert report["readiness_overstated"] is True
