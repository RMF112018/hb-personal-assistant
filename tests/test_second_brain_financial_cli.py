"""Phase 08C — operator-usable financial CLI surfaces.

Verifies the six read-only financial commands emit a consistent operator envelope
(project key, advisory label, guardrails, no-determination attestations, evidence
paths) in JSON and a human-readable form, with builders stubbed so the tests stay
hermetic (no real evidence writes). The no-writeback generator itself is tested for
real in test_phase_08c_financial_no_writeback.py.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app

_FC = "hb_assistant.construction.second_brain.financial_completeness"
_RR = "hb_assistant.construction.second_brain.financial_review_routing"
_NW = "hb_assistant.construction.second_brain.financial_no_writeback"
_DQ = "hb_assistant.construction.second_brain.data_quality"


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "second_brain.sqlite")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _redirect_store_to_tmp(monkeypatch: pytest.MonkeyPatch, db_path: str) -> None:
    from hb_assistant.store import connection as conn_mod
    from hb_assistant.store import migrator as mig_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(Path(db_path))

    monkeypatch.setattr(mig_mod, "get_connection", _get)


def _stub_builders(monkeypatch: pytest.MonkeyPatch, *, proof_passed: bool = True) -> None:
    monkeypatch.setattr(
        f"{_FC}.run_financial_fact_readiness_agent",
        lambda *a, **k: {
            "run_id": "r-readiness",
            "status": "succeeded",
            "items_evaluated": 3,
            "review_required_count": 1,
            "proof_path": "EVIDENCE/financial-readiness-agent-proof.json",
        },
    )
    monkeypatch.setattr(f"{_FC}.build_source_coverage_snapshot", lambda *a, **k: {"rows": 0})
    monkeypatch.setattr(
        f"{_FC}.build_financial_source_coverage_matrix",
        lambda *a, **k: {"summary": {"by_status": {"covered_ready": 2}}, "total_sources": 2},
    )
    monkeypatch.setattr(
        f"{_FC}.build_financial_exposure_mart_preview",
        lambda *a, **k: {"summary": {"total_items": 0}},
    )
    monkeypatch.setattr(
        f"{_RR}.build_financial_review_required_proof",
        lambda *a, **k: {
            "run_id": "r-review",
            "proof_path": "EVIDENCE/financial-review-required-proof.md",
            "items_evaluated": 5,
            "review_required_count": 2,
            "by_trigger": {"missing_source_field_path": 2},
            "by_tier": {"operator_review": 2},
            "by_confidence": {"medium": 2},
        },
    )
    monkeypatch.setattr(
        f"{_DQ}.build_phase_08c_gates_proof",
        lambda *a, **k: {
            "ok": True,
            "proof_passed": True,
            "schema_version": 36,
            "schema_version_expected": 35,
            "status_counts": {"pass": 1, "warning": 0, "fail_blocking": 0, "deferred_not_blocking": 0},
            "by_field_status": {"forecast_readiness": "pass"},
            "required_fields_covered": True,
            "readiness_overstated": False,
            "missing_required_evidence": [],
            "proof_path": "EVIDENCE/phase-08c-gates-proof.md",
            "evidence_paths": ["EVIDENCE/phase-08c-gates-proof.json"],
        },
    )
    monkeypatch.setattr(
        f"{_NW}.build_financial_no_writeback_proof",
        lambda *a, **k: {
            "proof_passed": proof_passed,
            "checks_detail": {"guard_columns": {"passed": proof_passed}},
            "proof_path": "EVIDENCE/financial-no-writeback-proof.md",
            "proof_json_path": "EVIDENCE/financial-no-writeback-proof.json",
        },
    )


_JSON_COMMANDS = [
    ["second-brain", "financial", "readiness"],
    ["second-brain", "financial", "coverage"],
    ["second-brain", "financial", "exposure-summary"],
    ["second-brain", "financial", "review-items"],
    ["second-brain", "financial", "no-writeback-proof"],
    ["second-brain", "data-quality", "phase-08c-gates"],
]


@pytest.mark.parametrize("cmd", _JSON_COMMANDS)
def test_financial_command_json_envelope(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str, cmd: list[str]
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    _stub_builders(monkeypatch)

    result = runner.invoke(app, [*cmd, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["phase"] == "08C"
    assert "project_key" in payload
    assert payload["advisory_only"] is True
    assert payload["guardrails"]["financial_determination_forbidden"] is True
    assert payload["guardrails"]["no_external_writeback"] is True
    # explicit no-determination / no-payment attestation block
    att = payload["attestations"]
    assert att["financial_determination_performed"] is False
    assert att["payment_decision_performed"] is False
    assert att["external_writeback_performed"] is False
    assert att["live_procore_call_performed"] is False
    assert payload["evidence_paths"]


@pytest.mark.parametrize("cmd", _JSON_COMMANDS)
def test_financial_command_human_output(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str, cmd: list[str]
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    _stub_builders(monkeypatch)

    result = runner.invoke(app, [*cmd, "--no-json"])
    assert result.exit_code == 0, result.output
    assert "Phase 08C" in result.output
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)


def test_financial_command_project_key_passthrough(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    _stub_builders(monkeypatch)

    result = runner.invoke(
        app, ["second-brain", "financial", "readiness", "--project", "tropical", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["project_key"] == "tropical"


def test_no_writeback_proof_exit_code_reflects_result(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)

    _stub_builders(monkeypatch, proof_passed=True)
    ok = runner.invoke(app, ["second-brain", "financial", "no-writeback-proof", "--json"])
    assert ok.exit_code == 0, ok.output
    assert json.loads(ok.output)["proof_passed"] is True

    _stub_builders(monkeypatch, proof_passed=False)
    fail = runner.invoke(app, ["second-brain", "financial", "no-writeback-proof", "--json"])
    assert fail.exit_code == 3
    assert json.loads(fail.output)["proof_passed"] is False
