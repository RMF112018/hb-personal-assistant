from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from hb_assistant.nas_mcp.artifact_tools import _runtime_manifest_build_kwargs
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.capability_registry import (
    CapabilityProfile,
    build_capability_registry,
    definitions_for_profile,
    direct_names_for_profile,
    gateway_names_for_profile,
    resolve_profile,
)
from hb_assistant.nas_mcp.freshness import capability_mode
from hb_assistant.nas_mcp.live_tool_surface import installed_tool_names, surface_profile_label
from hb_assistant.nas_mcp.runtime_attestation import build_runtime_attestation
from hb_assistant.nas_mcp.tool_registration import (
    _validate_registered_schema_bindings,
    live_tool_schema_index,
    register_nas_mcp_tools,
    registered_tool_binding_map,
)
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

INTERNAL_DIRECT_NAMES = {
    "assistant_get_action_stage",
    "assistant_get_action_stage_citations",
    "assistant_get_action_stage_export",
    "assistant_get_action_stage_items",
    "assistant_get_action_stage_summary",
    "assistant_get_context_pack",
    "assistant_get_context_pack_items",
    "assistant_get_draft",
    "assistant_get_draft_citations",
    "assistant_get_draft_export",
    "assistant_get_draft_sections",
    "assistant_get_draft_summary",
    "assistant_get_effective_review_state",
    "assistant_get_feedback",
    "assistant_get_feedback_export",
    "assistant_get_feedback_recommendations",
    "assistant_get_feedback_summary",
    "assistant_get_feedback_targets",
    "assistant_get_intelligence_projection",
    "assistant_get_intelligence_projection_export",
    "assistant_get_intelligence_projection_items",
    "assistant_get_intelligence_summary",
    "assistant_get_quality",
    "assistant_get_quality_export",
    "assistant_get_quality_findings",
    "assistant_get_quality_summary",
    "assistant_get_quality_targets",
    "assistant_get_research_packet",
    "assistant_get_research_packet_citations",
    "assistant_get_research_packet_export",
    "assistant_get_research_packet_items",
    "assistant_get_research_packet_summary",
    "assistant_get_review_dispositions",
    "assistant_get_review_item",
    "assistant_get_review_summary",
    "assistant_get_workflow_artifacts",
    "assistant_get_workflow_context",
    "assistant_get_workflow_policy",
    "assistant_get_workflow_summary",
    "assistant_list_action_stages",
    "assistant_list_context_packs",
    "assistant_list_drafts",
    "assistant_list_enrichment_review_items",
    "assistant_list_feedback",
    "assistant_list_intelligence_projections",
    "assistant_list_quality",
    "assistant_list_research_packets",
    "assistant_list_review_items",
    "assistant_list_workflows",
    "assistant_route_workflow",
    "assistant_source_folder_map",
    "assistant_source_folder_summary",
    "assistant_source_project_map",
    "assistant_source_quality",
    "assistant_source_root_map",
    "assistant_source_scope_explain",
    "assistant_source_search_route",
    "pa_prompt_route",
    "pa_prompt_route_explain",
    "pa_tool_family_get",
    "pa_tool_manifest_freshness_check",
    "pa_tool_manifest_get",
    "pa_tool_manifest_refresh_promote",
    "pa_tool_manifest_refresh_stage",
    "pa_tool_manifest_review_plan",
    "pa_tool_manifest_tool_help",
    "pa_tool_manifest_workflow_get",
    "pa_tool_surface_freshness_check",
    "pa_tool_surface_runtime_attestation",
    "pa_workflow_recipe_get",
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
    assert names == INTERNAL_DIRECT_NAMES
    assert names == set(direct_names_for_profile(CapabilityProfile.INTERNAL))
    assert len(names) == 70
    payload = "\n".join(sorted(names)) + "\n"
    assert hashlib.sha256(payload.encode()).hexdigest() == (
        "8245f234c87ef87ba2ab17e61a3160033da4499fae8b73ef226528d8b3de2f4e"
    )


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("frontier-v1", FRONTIER_NAMES),
        ("legacy-v12", None),
        ("internal", INTERNAL_DIRECT_NAMES),
    ],
)
def test_manager_collector_fastmcp_and_live_surface_parity(
    tmp_path: Path,
    profile: str,
    expected: set[str] | None,
) -> None:
    mcp, _broker, config, names = _registered_surface(tmp_path, profile)
    manager_names = set(mcp._tool_manager._tools)
    collector_names = {tool.name for tool in mcp._tool_manager.list_tools()}
    derived = set(direct_names_for_profile(profile))
    assert names == manager_names == collector_names == installed_tool_names(config) == derived
    if expected is not None:
        assert names == expected
    else:
        assert len(names) == 185


def test_registered_binding_map_fails_on_missing_callable(tmp_path: Path) -> None:
    mcp, _broker, _config, names = _registered_surface(tmp_path, "frontier-v1")
    removed = mcp._tool_manager._tools.pop(sorted(names)[0])
    with pytest.raises(RuntimeError, match="binding set"):
        _validate_registered_schema_bindings(mcp, CapabilityProfile.FRONTIER_V1)
    mcp._tool_manager._tools[removed.name] = removed


def test_registered_binding_map_fails_on_wrong_callable(tmp_path: Path) -> None:
    mcp, _broker, _config, names = _registered_surface(tmp_path, "frontier-v1")
    name = sorted(names)[0]
    original = mcp._tool_manager._tools[name].fn
    mcp._tool_manager._tools[name].fn = test_registered_binding_map_fails_on_wrong_callable
    with pytest.raises(RuntimeError, match="handler module mismatch"):
        _validate_registered_schema_bindings(mcp, CapabilityProfile.FRONTIER_V1)
    mcp._tool_manager._tools[name].fn = original


def test_registered_binding_map_fails_on_duplicate_callable(tmp_path: Path) -> None:
    mcp, _broker, _config, names = _registered_surface(tmp_path, "frontier-v1")
    bindings = registered_tool_binding_map(mcp)
    assert set(bindings) == names
    first, second = sorted(names)[:2]
    original = mcp._tool_manager._tools[second].fn
    mcp._tool_manager._tools[second].fn = mcp._tool_manager._tools[first].fn
    with pytest.raises(RuntimeError, match="duplicate callable binding|handler symbol mismatch"):
        _validate_registered_schema_bindings(mcp, CapabilityProfile.FRONTIER_V1)
    mcp._tool_manager._tools[second].fn = original


def test_profile_count_documentation_matches_registry_truth() -> None:
    registry = build_capability_registry()
    gates = {item.feature_gate: True for item in registry.definitions if item.feature_gate}
    counts = {
        profile.value: len(direct_names_for_profile(profile, gates))
        for profile in CapabilityProfile
    }
    document = (
        Path(__file__).resolve().parents[1]
        / "docs/architecture/mcp-capability-profiles.md"
    ).read_text()
    assert f"| `frontier-v1` | {counts['frontier-v1']} |" in document
    assert f"| `legacy-v12` | {counts['legacy-v12']} |" in document
    assert f"| `internal` | {counts['internal']} |" in document


def test_explicit_profile_is_reported_consistently_across_structural_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HB_MCP_CAPABILITY_PROFILE", "frontier-v1")
    _mcp, broker, config, names = _registered_surface(tmp_path, "legacy-v12")
    assert len(names) == 185
    assert config.capability_profile is CapabilityProfile.LEGACY_V12
    status = broker.dispatch("hb_mcp_status", {})["result"]
    assert status["exposure_profile"]["capability_profile"] == "legacy-v12"
    assert surface_profile_label(config).endswith("+legacy-v12")
    assert _runtime_manifest_build_kwargs(config)["surface_profile"].endswith("+legacy-v12")
    assert capability_mode(config)["exposure_profile"]["capability_profile"] == "legacy-v12"
    assert build_runtime_attestation(config)["capability_profile"] == "legacy-v12"


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
