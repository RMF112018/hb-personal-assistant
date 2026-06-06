"""Phase 09 Addendum — daily-brief MCP handoff operator status + drift cleanup tests."""

from __future__ import annotations

import json
import re

from hb_assistant.construction.second_brain.daily_brief.mcp_handoff_status import (
    build_daily_brief_mcp_handoff_status,
)
from hb_assistant.construction.second_brain.phase_09_gates import build_phase_09_gates_proof
from hb_assistant.construction.second_brain.phase_09_operator_status import (
    evaluate_phase_09_operator_status,
)
from hb_assistant.store.migrator import SQLiteMigrator

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)

_REQUIRED_FIELDS = (
    "daily_brief_packet_status",
    "daily_brief_mcp_handoff_status",
    "claude_rendering_template_status",
    "rendered_brief_quality_status",
    "rendered_output_import_status",
)

_SUBSTRATE_KEYS = {
    "schema_substrate",
    "coverage_substrate",
    "quality_substrate",
    "handoff_substrate",
    "production_readiness",
}


def test_status_fields_exist() -> None:
    report = build_daily_brief_mcp_handoff_status(write_evidence=False)
    for f in _REQUIRED_FIELDS:
        assert f in report, f
    assert "gates" in report and "status_counts" in report


def test_handoff_proof_status_is_visible() -> None:
    report = build_daily_brief_mcp_handoff_status(write_evidence=False)
    assert report["daily_brief_mcp_handoff_status"] in (
        "missing",
        "available",
        "proof_passed",
        "blocked",
    )
    gate_names = {g["gate_name"] for g in report["gates"]}
    assert "mcp_handoff_proof" in gate_names
    assert "no_raw_no_writeback" in gate_names


def test_no_readiness_overstatement() -> None:
    report = build_daily_brief_mcp_handoff_status(write_evidence=False)
    assert report["readiness_overstated"] is False
    assert report["readiness_categories"]["production_readiness"] is False
    assert report["substrate_detail"]["production_readiness"] is False


def test_no_raw_no_writeback_failures_remain_blocking() -> None:
    # The gate mapping marks the safety gate fail_blocking unless both proofs pass.
    report = build_daily_brief_mcp_handoff_status(write_evidence=False)
    safety = next(g for g in report["gates"] if g["gate_name"] == "no_raw_no_writeback")
    if report["daily_brief_mcp_handoff_status"] == "blocked":
        assert safety["gate_status"] == "fail_blocking"
        assert report["handoff_closeout_ok"] is False
    else:
        assert safety["gate_status"] == "pass"


def test_rendered_import_disabled_reported_honestly() -> None:
    report = build_daily_brief_mcp_handoff_status(write_evidence=False)
    assert report["rendered_output_import_status"] in ("deferred", "not_supported")
    import_gate = next(g for g in report["gates"] if g["gate_name"] == "rendered_output_import")
    assert import_gate["gate_status"] == "deferred_not_blocking"


def test_gates_and_operator_status_terminology_consistent(tmp_path) -> None:
    db = str(tmp_path / "operator.sqlite")
    SQLiteMigrator(db_path=db).apply()
    gates = build_phase_09_gates_proof(db_path=db, write_evidence=False)
    operator = evaluate_phase_09_operator_status(db_path=db)
    # Both core commands now expose the identical distinguished substrate_detail shape.
    assert set(gates["substrate_detail"]) == _SUBSTRATE_KEYS
    assert set(operator["substrate_detail"]) == _SUBSTRATE_KEYS
    # And they agree on the reconciled categories.
    for key in (
        "schema_substrate",
        "coverage_substrate",
        "quality_substrate",
        "production_readiness",
    ):
        assert gates["substrate_detail"][key] == operator["substrate_detail"][key], key
    # Legacy field retained for back-compat.
    assert "phase_09_substrate_status" in gates
    assert "phase_09_substrate_status" in operator


def test_status_is_metadata_only_and_clean() -> None:
    report = build_daily_brief_mcp_handoff_status(write_evidence=False)
    assert report["read_only"] is True
    assert report["makes_determination"] is False
    assert not _SECRET_OR_URL.search(json.dumps(report, default=str))


def test_writes_evidence_artifacts(tmp_path) -> None:
    report = build_daily_brief_mcp_handoff_status(evidence_dir=str(tmp_path), write_evidence=True)
    assert (tmp_path / "daily-brief-mcp-handoff-operator-status.json").exists()
    assert (tmp_path / "daily-brief-mcp-handoff-operator-status.md").exists()
    assert "handoff_closeout_ok" in report
