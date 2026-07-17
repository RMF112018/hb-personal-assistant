"""PR-4 — manifest schema parity with frozen registration index (F-008)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dataclasses

import pytest
from mcp.server.fastmcp import FastMCP

from hb_assistant.nas_mcp.artifact_tools import dispatch_manifest_tool
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.capability_registry import CapabilityProfile
from hb_assistant.nas_mcp.live_tool_surface import build_tool_index, manifest_schema_parity_check
from hb_assistant.nas_mcp.tool_registration import (
    register_nas_mcp_tools,
    schema_index_frozen,
    seed_frozen_schema_index,
)
from tests.n8c23_helpers import make_env


@pytest.fixture(autouse=True)
def _clear_frozen_index() -> None:
    seed_frozen_schema_index({})
    yield
    seed_frozen_schema_index({})


def test_parity_fails_when_schema_index_not_frozen(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    rep = manifest_schema_parity_check(env["config"])
    assert rep["ok"] is False
    assert rep["reason"] == "schema_index_not_frozen"


def test_for_manifest_reads_required_args_from_frozen_index_only(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env["config"].capability_profile = CapabilityProfile.LEGACY_V12
    seed_frozen_schema_index({
        "assistant_get_decision": {
            "description": "Retrieve one decision by id.\n",
            "input_schema": {
                "properties": {"decision_id": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["decision_id"],
            },
        },
    })
    idx = build_tool_index(env["config"], for_manifest=True)
    assert idx["assistant_get_decision"]["required_args"] == ["decision_id"]
    # Partial index seed is intentionally incomplete — full parity is validated after registration.
    assert manifest_schema_parity_check(env["config"])["ok"] is False


def test_parity_detects_required_args_drift(tmp_path: Path, monkeypatch) -> None:
    import hb_assistant.nas_mcp.live_tool_surface as lts

    env = make_env(tmp_path)
    env["config"].capability_profile = CapabilityProfile.LEGACY_V12
    seed_frozen_schema_index({
        "pa_prompt_route": {
            "description": "Route a prompt.\n",
            "input_schema": {
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
            },
        },
    })
    real_build = lts.build_live_tool_surface

    def _tampered(config: Any, *, for_manifest: bool = False) -> dict[str, Any]:
        surface = real_build(config, for_manifest=for_manifest)
        if for_manifest and "pa_prompt_route" in surface:
            st = surface["pa_prompt_route"]
            surface["pa_prompt_route"] = dataclasses.replace(st, required_args=("wrong_arg",))
        return surface

    monkeypatch.setattr(lts, "build_live_tool_surface", _tampered)
    rep = manifest_schema_parity_check(env["config"])
    assert rep["ok"] is False
    assert rep["reason"] == "schema_parity_mismatch"
    assert rep["diffs"][0]["tool_name"] == "pa_prompt_route"


def test_refresh_stage_auto_freezes_schema_index(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    stg = dispatch_manifest_tool(env["config"], "pa_tool_manifest_refresh_stage", {})
    assert schema_index_frozen()
    assert stg["status"] == "staged"
    assert stg.get("schema_parity", {}).get("ok") is True


def test_refresh_stage_succeeds_after_registration(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    mcp = FastMCP("n8c23-parity")
    register_nas_mcp_tools(mcp, NasMcpBroker(env["config"]), capability_profile="legacy-v12")
    assert schema_index_frozen()
    stg = dispatch_manifest_tool(env["config"], "pa_tool_manifest_refresh_stage", {})
    assert stg["status"] == "staged"
    assert stg.get("schema_parity", {}).get("ok") is True
