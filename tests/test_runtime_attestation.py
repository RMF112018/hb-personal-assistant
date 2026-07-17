"""Runtime tool-surface attestation (P1 §3.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.capability_registry import definitions_for_profile
from hb_assistant.nas_mcp.prompt_routing_tools import PROMPT_ROUTING_TOOLS, dispatch_prompt_routing_tool
from hb_assistant.nas_mcp.runtime_attestation import build_runtime_attestation
from hb_assistant.obsidian_mcp.tool_surface_freshness import check_tool_surface
from tests.n8c23_helpers import make_env


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    return make_env(tmp_path)


def test_attestation_passes_on_migrated_surface(env: dict) -> None:
    report = build_runtime_attestation(env["config"])
    assert report["tested_tool_count"] > 0
    assert report["failed_count"] == 0, [
        r for r in report["per_tool"] if r["status"] == "failed"
    ]
    assert report["attestation_ok"] is True
    assert report["client_writes_must_be_blocked"] is False
    assert "runtime_commit" in report
    expected_aliases = sum(
        item.is_alias for item in definitions_for_profile(report["capability_profile"])
    )
    assert report["direct_gateway_parity"]["alias_pairs_checked"] == expected_aliases


def test_attestation_tool_registered_in_routing_layer() -> None:
    assert "pa_tool_surface_runtime_attestation" in PROMPT_ROUTING_TOOLS


def test_attestation_dispatch_round_trip(env: dict) -> None:
    out = dispatch_prompt_routing_tool(env["config"], "pa_tool_surface_runtime_attestation", {})
    assert out["attestation_ok"] is True
    assert out["passed_count"] == out["tested_tool_count"]


def test_execution_attestation_stale_blocks_freshness() -> None:
    live = {"pa_output_stage": None, "pa_prompt_route": None}
    rep = check_tool_surface(
        live,
        stored_entries=None,
        check_workflow_coverage=False,
        attestation_ok=False,
        attestation_failed_count=2,
    )
    assert rep["categories"]["execution_attestation"] is True
    assert rep["stale"] is True
    assert rep["category_status"]["execution_attestation"] == "stale"
    assert rep["client_writes_must_be_blocked"] is True


def test_execution_attestation_current_when_ok() -> None:
    live = {"pa_output_stage": None}
    rep = check_tool_surface(
        live,
        stored_entries=None,
        check_workflow_coverage=False,
        attestation_ok=True,
        attestation_failed_count=0,
        attestation_age_seconds=10,
    )
    assert rep["categories"]["execution_attestation"] is False
    assert rep["category_status"]["execution_attestation"] == "current"
    assert rep["client_writes_must_be_blocked"] is False
