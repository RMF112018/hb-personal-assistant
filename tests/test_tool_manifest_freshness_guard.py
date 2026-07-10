"""Tool-surface freshness guard — drift detection + write fail-closed."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt
from hb_assistant.obsidian_mcp.tool_surface_freshness import check_tool_surface


def _base_entries(groups: dict[str, str | None]) -> dict[str, dict]:
    from hb_assistant.obsidian_mcp.tool_entry_manifest import build_tool_entry
    return {n: build_tool_entry(n, g) for n, g in groups.items()}


LIVE = {
    "assistant_get_decision": "decision_memory",
    "pa_output_stage": None,
    "pa_output_list": None,
    "pa_prompt_route": None,
    "hb_output_write_file": None,
}


def test_matching_surface_without_checksum_baseline_is_indeterminate() -> None:
    entries = _base_entries(LIVE)
    rep = check_tool_surface(LIVE, stored_entries=entries, check_workflow_coverage=False)
    assert rep["stale"] is False
    assert rep["staleness_state"] == "indeterminate"
    assert "semantic_checksum" in rep["unchecked_categories"]


def test_matching_surface_with_checksums_is_current() -> None:
    from hb_assistant.obsidian_mcp.client_tool_manifest import build_live_surface_fingerprints

    entries = _base_entries(LIVE)
    fps = build_live_surface_fingerprints(
        {n: {"group": g} for n, g in LIVE.items()},
        surface_profile="test",
        gate_state_snapshot={},
        gateway_allowlist=sorted(LIVE),
    )
    rep = check_tool_surface(
        LIVE,
        stored_entries=entries,
        check_workflow_coverage=False,
        live_semantic_checksum=fps["semantic_surface_checksum"],
        stored_semantic_checksum=fps["semantic_surface_checksum"],
        live_exposure_checksum=fps["exposure_checksum"],
        stored_exposure_checksum=fps["exposure_checksum"],
        live_gateway_allowlist=frozenset(LIVE),
        stored_gateway_allowlist=frozenset(LIVE),
        live_profile="test",
        stored_profile="test",
        live_runtime_commit="deadbeef",
        stored_runtime_commit="deadbeef",
    )
    assert rep["stale"] is False
    assert rep["staleness_state"] == "current"


def test_added_tool_makes_stale() -> None:
    entries = _base_entries(LIVE)
    live2 = dict(LIVE, pa_output_new_thing=None)
    rep = check_tool_surface(live2, stored_entries=entries, check_workflow_coverage=False)
    assert rep["stale"] is True
    assert "pa_output_new_thing" in rep["added_tools"]


def test_removed_tool_makes_stale() -> None:
    entries = _base_entries(LIVE)
    live2 = {k: v for k, v in LIVE.items() if k != "pa_output_stage"}
    rep = check_tool_surface(live2, stored_entries=entries, check_workflow_coverage=False)
    assert rep["stale"] is True
    assert "pa_output_stage" in rep["removed_tools"]


def test_family_change_makes_stale() -> None:
    entries = _base_entries(LIVE)
    entries["pa_output_stage"]["tool_family"] = "canonical_promotion"  # simulate stored disagreeing
    rep = check_tool_surface(LIVE, stored_entries=entries, check_workflow_coverage=False)
    assert rep["stale"] is True
    assert "pa_output_stage" in rep["family_changed_tools"]


def test_gateway_scope_change_makes_stale() -> None:
    rep = check_tool_surface(
        LIVE,
        live_gateway_allowlist=frozenset({"pa_output_stage", "pa_output_commit"}),
        stored_gateway_allowlist=frozenset({"pa_output_stage"}),
    )
    assert rep["tool_surface_gateway_current"] is False
    assert rep["stale"] is True


def test_stale_surface_blocks_write_route_not_read() -> None:
    stale = {"stale": True, "staleness_state": "stale", "warnings": ["drift"]}
    write_plan = route_prompt("Generate a Word document and save it", freshness=stale)
    assert write_plan["freshness"]["write_blocked_by_staleness"] is True
    read_plan = route_prompt("find the source file for the contract", freshness=stale)
    assert read_plan["freshness"]["write_blocked_by_staleness"] is False


def test_indeterminate_surface_blocks_write_route_not_read() -> None:
    indeterminate = {"stale": False, "staleness_state": "indeterminate", "warnings": ["semantic_checksum_indeterminate"]}
    write_plan = route_prompt("Generate a Word document and save it", freshness=indeterminate)
    assert write_plan["freshness"]["write_blocked_by_staleness"] is True
    read_plan = route_prompt("find the source file for the contract", freshness=indeterminate)
    assert read_plan["freshness"]["write_blocked_by_staleness"] is False


def test_persisted_manifest_agrees_with_live_surface_freshness(tmp_path) -> None:
    from hb_assistant.nas_mcp.artifact_tools import _build_tool_index, _runtime_manifest_build_kwargs
    from hb_assistant.nas_mcp.prompt_routing_tools import live_freshness
    from hb_assistant.obsidian_mcp.client_tool_manifest import ClientToolManifestRepository, build_manifest
    from tests.n8c23_helpers import make_env

    from hb_assistant.nas_mcp.broker import runtime_commit

    env = make_env(tmp_path)
    repo = ClientToolManifestRepository(env["db"])
    m = build_manifest(
        _build_tool_index(env["config"]),
        runtime_commit=runtime_commit(),
        now="2026-07-10T00:00:00+00:00",
        **_runtime_manifest_build_kwargs(),
    )
    repo.save_manifest(m)
    fr = live_freshness(env["config"])
    assert fr["stale"] is False, fr.get("warnings")


def test_manifest_entries_match_freshness_baseline() -> None:
    """Promoted manifest entries must agree with build_tool_entry classification fields."""
    from hb_assistant.obsidian_mcp.canonical_tool_specs import tool_spec_public_entry
    from hb_assistant.nas_mcp.live_tool_surface import build_live_tool_surface
    from hb_assistant.nas_mcp.config import NasMcpConfig

    surface = build_live_tool_surface(NasMcpConfig.from_env())
    groups = {name: st.group for name, st in surface.items()}
    stored = {
        name: {
            "tool_name": entry["tool_name"],
            "tool_family": entry["tool_family"],
            "read_write_class": entry["read_write_class"],
            "safety_class": entry["safety_class"],
        }
        for name, st in surface.items()
        for entry in [tool_spec_public_entry(name, st.group)]
    }
    rep = check_tool_surface(groups, stored_entries=stored, check_workflow_coverage=False)
    assert rep["class_changed_tools"] == [], rep["class_changed_tools"]
    assert rep["family_changed_tools"] == [], rep["family_changed_tools"]
    assert rep["stale"] is False, rep["warnings"]
