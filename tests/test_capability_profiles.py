from __future__ import annotations

from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.capability_registry import (
    CapabilityProfile,
    build_capability_registry,
    definitions_for_profile,
    gateway_names_for_profile,
    resolve_profile,
)
from hb_assistant.nas_mcp.live_tool_surface import installed_tool_names
from hb_assistant.nas_mcp.tool_registration import live_tool_schema_index, register_nas_mcp_tools
from tests.n8c23_helpers import make_env

FRONTIER_NAMES = {
    "assistant_source_file_metadata",
    "assistant_source_file_read",
    "assistant_source_file_search",
    "assistant_source_files_list",
    "assistant_source_index_health",
    "assistant_source_roots_list",
    "assistant_source_status",
    "hb_assistant_catalog",
    "hb_assistant_tool_help",
    "hb_capability_mode",
    "hb_data_freshness",
    "hb_mcp_status",
}


def test_default_and_explicit_profile_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_MCP_CAPABILITY_PROFILE", raising=False)
    assert resolve_profile() is CapabilityProfile.FRONTIER_V1
    monkeypatch.setenv("HB_MCP_CAPABILITY_PROFILE", "legacy-v12")
    assert resolve_profile() is CapabilityProfile.LEGACY_V12
    monkeypatch.setenv("HB_MCP_CAPABILITY_PROFILE", "invalid")
    with pytest.raises(ValueError, match="invalid MCP capability profile"):
        resolve_profile()


def test_frontier_v1_is_exact_twelve_name_public_surface() -> None:
    definitions = definitions_for_profile(CapabilityProfile.FRONTIER_V1)
    assert {item.registered_name for item in definitions} == FRONTIER_NAMES
    assert gateway_names_for_profile(CapabilityProfile.FRONTIER_V1) == FRONTIER_NAMES
    assert all(not item.is_alias for item in definitions)
    assert all(item.group != "vault_adapter" for item in definitions)
    assert "hb_assistant_tool_query" not in FRONTIER_NAMES


def test_legacy_v12_preserves_all_185_names_with_gates_enabled() -> None:
    registry = build_capability_registry()
    gates = {item.feature_gate: True for item in registry.definitions if item.feature_gate}
    definitions = definitions_for_profile(CapabilityProfile.LEGACY_V12, gates)
    assert len(definitions) == 185
    assert {item.registered_name for item in definitions} == set(registry.by_name)


def test_internal_is_never_default_and_excluded_from_frontier() -> None:
    internal = {
        item.registered_name for item in definitions_for_profile(CapabilityProfile.INTERNAL)
    }
    frontier = {
        item.registered_name for item in definitions_for_profile(CapabilityProfile.FRONTIER_V1)
    }
    assert internal
    assert internal.isdisjoint(frontier)


def test_feature_gate_can_only_reduce_profile() -> None:
    enabled = {item.registered_name for item in definitions_for_profile("frontier-v1")}
    disabled = {
        item.registered_name
        for item in definitions_for_profile(
            "frontier-v1", {"HB_MCP_ASSISTANT_SOURCE_CONNECTOR": False}
        )
    }
    assert disabled == FRONTIER_NAMES - {
        name for name in FRONTIER_NAMES if name.startswith("assistant_source_")
    }
    assert disabled < enabled


def _registered_surface(tmp_path: Path, profile: str | None):
    environment = make_env(tmp_path)
    mcp = FastMCP(f"batch1-{profile or 'default'}", json_response=True, stateless_http=True)
    broker = NasMcpBroker(environment["config"])
    register_nas_mcp_tools(
        mcp,
        broker,
        capability_profile=profile,
    )
    names = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert set(live_tool_schema_index()) == names
    assert installed_tool_names(environment["config"]) == names
    return mcp, broker, environment["config"], names


def test_default_startup_registers_exact_frontier_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HB_MCP_CAPABILITY_PROFILE", raising=False)
    assert _registered_surface(tmp_path, None)[-1] == FRONTIER_NAMES


def test_legacy_rollback_registers_exact_185_name_surface(tmp_path: Path) -> None:
    names = _registered_surface(tmp_path, "legacy-v12")[-1]
    assert len(names) == 185
    assert names == set(build_capability_registry().by_name)


def test_internal_profile_registers_only_internal_members(tmp_path: Path) -> None:
    names = _registered_surface(tmp_path, "internal")[-1]
    assert names == {
        item.registered_name for item in definitions_for_profile(CapabilityProfile.INTERNAL)
    }


@pytest.mark.parametrize(
    ("profile", "expected_tools", "expected_assistant", "expected_groups"),
    [("frontier-v1", 12, 7, 1), ("legacy-v12", 185, 87, 14)],
)
def test_catalog_status_and_gateway_counts_follow_profile(
    tmp_path: Path,
    profile: str,
    expected_tools: int,
    expected_assistant: int,
    expected_groups: int,
) -> None:
    mcp, broker, _config, names = _registered_surface(tmp_path, profile)
    tools = {tool.name: tool for tool in mcp._tool_manager.list_tools()}
    catalog = tools["hb_assistant_catalog"].fn()
    status = broker.dispatch("hb_mcp_status", {})["result"]
    assert len(names) == expected_tools
    assert catalog["canonical_assistant_tool_count"] == expected_assistant
    assert catalog["group_count"] == expected_groups
    assert catalog["gateway_allowlist_count"] == len(gateway_names_for_profile(profile))
    assert status["assistant_client_exposed_tool_count"] == expected_assistant
    assert status["assistant_client_missing_tool_count"] == 0
