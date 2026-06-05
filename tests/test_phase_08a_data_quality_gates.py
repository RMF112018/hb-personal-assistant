"""Phase 08A Prompt 14 — second-brain data-quality gate evaluator."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.data_quality import (
    GATE_NAMES,
    build_phase_08a_gates_proof,
    evaluate_phase_08a_data_quality_gates,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_report_covers_all_contract_gates() -> None:
    report = evaluate_phase_08a_data_quality_gates()
    contract = load_phase_08a_contract("data_quality_gates_contract")
    assert report["required_fields_covered"] is True
    assert sorted(report["by_field_status"].keys()) == sorted(contract["required_fields"])
    assert sorted(GATE_NAMES) == sorted(contract["required_fields"])


def test_statuses_distinguish_pass_warning_fail_deferred() -> None:
    report = evaluate_phase_08a_data_quality_gates()
    counts = report["status_counts"]
    assert set(counts) == {"pass", "warning", "fail_blocking", "deferred_not_blocking"}
    assert counts["pass"] >= 1
    assert counts["warning"] >= 1  # synthesis offline/mock -> warning
    assert counts["deferred_not_blocking"] >= 1
    assert counts["fail_blocking"] == 0
    assert report["ok"] is True


def test_no_readiness_overstatement() -> None:
    report = evaluate_phase_08a_data_quality_gates()
    assert report["readiness_overstated"] is False
    # Offline/mock synthesis must NOT be reported as pass.
    if report["synthesis_mode"] != "live":
        assert report["by_field_status"]["synthesis_liveness"] == "warning"
    # Unimplemented surfaces are deferred, never pass.
    for deferred in ("mcp_exposure", "model_call_receipt_persistence", "automation_hardening"):
        assert report["by_field_status"][deferred] == "deferred_not_blocking"


def test_all_required_surfaces_present() -> None:
    report = evaluate_phase_08a_data_quality_gates()
    by = report["by_field_status"]
    for surface in (
        "runtime_readiness",
        "agent_registry",
        "model_profile",
        "retrieval",
        "research_packet",
        "evaluation",
        "memory_provenance",
        "daily_brief_handoff",
    ):
        assert surface in by


def test_report_carries_no_raw_content() -> None:
    blob = json.dumps(evaluate_phase_08a_data_quality_gates(), default=str)
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
    proof = build_phase_08a_gates_proof()
    assert proof["proof_passed"] is True
    assert proof["gates_distinguish_pass_warning_fail_deferred"] is True
    assert proof["no_readiness_overstatement"] is True
    assert proof["required_fields_covered"] is True
    assert proof["no_raw_content"] is True


def test_cli_phase_08a_gates_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "data-quality", "phase-08a-gates", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain data-quality phase-08a-gates"
    assert payload["ok"] is True
    assert payload["required_fields_covered"] is True
    assert payload["status_counts"]["fail_blocking"] == 0
    assert payload["readiness_overstated"] is False
