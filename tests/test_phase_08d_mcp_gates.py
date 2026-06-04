"""Phase 08D MCP-bridge data-quality gates.

Proves the registry/contract-level gate evaluator covers all 14 contract gates with the
pass/warning/fail_blocking/deferred_not_blocking taxonomy and no readiness overstatement.
After Prompt 15 every gate passes (no_raw_access P13, no_writeback P14, validation_matrix
P15): the count is 14 pass / 0 deferred regardless of the optional MCP SDK, while
``ready_to_serve`` tracks the SDK — true when installed (operational), false otherwise
(``mcp_sdk_not_installed``). The evaluator never dispatches the heavyweight
synthesis/retrieval workflow proofs.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain import data_quality
from hb_assistant.construction.second_brain.contracts import load_phase_08d_contract
from hb_assistant.construction.second_brain.data_quality import (
    build_phase_08d_gates_proof,
    evaluate_phase_08d_data_quality_gates,
)

runner = CliRunner()

# Prompt 15 wired the last gate (validation_matrix) to a live proof — no gate is deferred.
_DEFERRED_GATES: set[str] = set()
_SDK_PRESENT = importlib.util.find_spec("mcp") is not None


def _evaluate(db: str) -> dict:
    return evaluate_phase_08d_data_quality_gates(db_path=db)


def test_evaluator_covers_all_fourteen_contract_gates() -> None:
    required = set(load_phase_08d_contract("data_quality_gates_contract")["required_gates"])
    assert len(required) == 14
    with tempfile.TemporaryDirectory() as td:
        report = _evaluate(str(Path(td) / "a.db"))
    assert set(report["by_field_status"]) == required
    counts = report["status_counts"]
    assert sum(counts.values()) == 14
    assert report["required_fields_covered"] is True


def test_all_gates_pass_with_no_deferral() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = _evaluate(str(Path(td) / "a.db"))
    by = report["by_field_status"]
    # Prompts 13/14/15: the three former readiness gates all pass.
    assert by["no_raw_access"] == "pass"
    assert by["no_writeback"] == "pass"
    assert by["validation_matrix"] == "pass"
    assert report["status_counts"]["deferred_not_blocking"] == 0
    assert report["status_counts"]["pass"] == 14


def test_ready_to_serve_tracks_sdk_and_is_never_overstated() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = _evaluate(str(Path(td) / "a.db"))
    blockers = report["serve_blockers"]
    # The deferred-era blockers are gone.
    assert "no_raw_access_proof_pending_prompt_13" not in blockers
    assert "no_mcp_writeback_proof_pending_prompt_14" not in blockers
    assert "full_validation_matrix_pending_prompt_15" not in blockers
    if _SDK_PRESENT:
        # Operational: every readiness gate passes and the SDK is present.
        assert report["ready_to_serve"] is True
        assert blockers == []
    else:
        # Base install: fail-closed on the optional SDK only.
        assert report["ready_to_serve"] is False
        assert blockers == ["mcp_sdk_not_installed"]


def test_ok_and_no_readiness_overstatement() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = _evaluate(str(Path(td) / "a.db"))
    assert report["ok"] is True
    assert report["readiness_overstated"] is False
    assert report["status_counts"]["fail_blocking"] == 0
    assert report["schema_version"] == report["schema_version_expected"]


def test_proof_passes_and_writes_guard_clean_artifacts() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_phase_08d_gates_proof(db_path=str(Path(td) / "a.db"), out_dir=td)
        assert proof["proof_passed"] is True
        assert proof["ok"] is True
        assert proof["ready_to_serve"] is _SDK_PRESENT
        assert set(proof["deferred_gates"]) == _DEFERRED_GATES
        # every stop check must be False (no missing-evidence pass, no overstatement, no
        # deferred gate masquerading as pass).
        assert all(v is False for v in proof["stop_checks"].values())

        json_path = Path(td) / "phase-08d-gates-proof.json"
        md_path = Path(td) / "phase-08d-gates-proof.md"
        assert json_path.exists() and md_path.exists()
        reloaded = json.loads(json_path.read_text())
        assert reloaded["proof"] == "phase_08d_data_quality_gates"
        assert len(reloaded["gates"]) == 14
        md = md_path.read_text()
        assert f"ready to serve: {str(_SDK_PRESENT).lower()}" in md.lower()


def test_evaluator_does_not_dispatch_heavyweight_proofs(monkeypatch) -> None:
    """The two synthesis/retrieval execution proofs must never be called by the evaluator."""
    import hb_assistant.construction.second_brain.mcp.proof as mcp_proof

    def _boom(*_args, **_kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("heavyweight proof dispatched from gate evaluator")

    monkeypatch.setattr(mcp_proof, "build_mcp_allowed_tools_proof", _boom)
    monkeypatch.setattr(mcp_proof, "build_mcp_resources_proof", _boom)
    with tempfile.TemporaryDirectory() as td:
        report = _evaluate(str(Path(td) / "a.db"))
    assert report["ok"] is True
    assert len(report["by_field_status"]) == 14


def test_missing_evidence_helper_flags_fail_blocking_reasons() -> None:
    gates = [
        data_quality._gate("schema_contracts", "fail_blocking", reason="SCHEMA_NOT_AT_EXPECTED"),
        data_quality._gate("denials", "pass"),
    ]
    assert data_quality._missing_required_evidence_08d(gates) == ["schema_contracts"]


def test_cli_phase_08d_gates_emits_passing_advisory_payload() -> None:
    result = runner.invoke(app, ["second-brain", "data-quality", "phase-08d-gates", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["proof_passed"] is True
    assert payload["ready_to_serve"] is _SDK_PRESENT
    assert len(payload["by_field_status"]) == 14
    assert set(payload["deferred_gates"]) == _DEFERRED_GATES
    assert payload["guardrails"]["no_readiness_overstatement"] is True
