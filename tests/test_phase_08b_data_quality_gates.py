"""Phase 08B Prompt 02 — phase-08b-gates (automation/observability substrate readiness)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.data_quality import (
    PHASE_08B_GATE_NAMES,
    build_phase_08b_gates_proof,
    evaluate_phase_08b_data_quality_gates,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_report_covers_all_contract_gates() -> None:
    report = evaluate_phase_08b_data_quality_gates()
    assert report["required_fields_covered"] is True
    assert sorted(report["by_field_status"].keys()) == sorted(PHASE_08B_GATE_NAMES)


def test_statuses_pass_and_defer_no_fail() -> None:
    counts = evaluate_phase_08b_data_quality_gates()["status_counts"]
    assert counts["pass"] >= 1
    assert counts["deferred_not_blocking"] >= 1
    assert counts["fail_blocking"] == 0


def test_no_readiness_overstatement() -> None:
    report = evaluate_phase_08b_data_quality_gates()
    assert report["readiness_overstated"] is False
    by = report["by_field_status"]
    # Execution surfaces owned by a later prompt must never be reported as pass.
    assert by["automation_execution"] == "deferred_not_blocking"
    assert by["launchd_install"] == "deferred_not_blocking"
    # Substrate surfaces this prompt ships are pass.
    assert by["agent_run_receipt_persistence"] == "pass"
    assert by["agent_model_receipt_persistence"] == "pass"


def test_gates_carry_structured_reason_codes() -> None:
    gates = {g["gate_name"]: g for g in evaluate_phase_08b_data_quality_gates()["gates"]}
    assert gates["agent_run_receipt_persistence"]["reason"] == "RECEIPT_PERSISTENCE_OK"
    assert (
        gates["automation_execution"]["reason"]
        == "HEALTH_RETRY_WEEKEND_ALERTING_EXECUTION_DEFERRED"
    )
    assert gates["launchd_install"]["reason"] == "REAL_LAUNCHD_INSTALL_DEFERRED"


def test_report_carries_no_raw_content() -> None:
    blob = json.dumps(evaluate_phase_08b_data_quality_gates(), default=str)
    for forbidden in (
        "signed_url",
        "download_url",
        "raw_body",
        "raw_prompt",
        "raw_response",
        "secret",
    ):
        assert forbidden not in blob


def test_proof_passes() -> None:
    proof = build_phase_08b_gates_proof()
    assert proof["proof_passed"] is True
    assert proof["readiness_overstated"] is False
    assert proof["no_raw_content"] is True


def test_cli_phase_08b_gates_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "data-quality", "phase-08b-gates", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain data-quality phase-08b-gates"
    assert payload["ok"] is True
    assert payload["required_fields_covered"] is True
    assert payload["status_counts"]["fail_blocking"] == 0
    assert payload["readiness_overstated"] is False
