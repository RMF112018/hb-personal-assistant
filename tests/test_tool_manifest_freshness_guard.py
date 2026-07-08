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


def test_matching_surface_is_current() -> None:
    entries = _base_entries(LIVE)
    rep = check_tool_surface(LIVE, stored_entries=entries, check_workflow_coverage=False)
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
