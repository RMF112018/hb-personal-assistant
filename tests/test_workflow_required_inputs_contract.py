"""CI guard: workflow required_inputs align with live/static tool schemas."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import required_args_for_tool
from hb_assistant.obsidian_mcp.workflow_recipe_manifest import WORKFLOWS

# Discovery-first: required_inputs apply to a later getter/read tool, not the list step.
_DISCOVERY_FIRST_GETTER: frozenset[str] = frozenset({
    "canonical_decision_retrieval",
    "canonical_preference_retrieval",
    "canonical_open_loop_retrieval",
})

# Workflow declares a minimum narrative; first tool has additional defaulted fields at extraction time.
_PARTIAL_FIRST_TOOL_INPUTS: dict[str, frozenset[str]] = {
    "document_session": frozenset({"session_summary"}),
}


def test_workflow_required_inputs_match_tool_schema_or_documented_exception() -> None:
    for wf in WORKFLOWS:
        wid = wf["workflow_id"]
        seq = list(wf.get("tool_sequence") or [])
        if not seq:
            continue
        wf_req = frozenset(wf.get("required_inputs") or ())
        first = seq[0]
        first_req = frozenset(required_args_for_tool(first))

        if wid in _DISCOVERY_FIRST_GETTER:
            if not wf_req:
                continue
            later_req: set[str] = set()
            for tool in seq[1:]:
                later_req.update(required_args_for_tool(tool))
            assert wf_req <= later_req, (wid, wf_req, later_req)
            continue

        if wid in _PARTIAL_FIRST_TOOL_INPUTS:
            assert wf_req == _PARTIAL_FIRST_TOOL_INPUTS[wid], (wid, wf_req)
            assert wf_req <= first_req, (wid, wf_req, first_req)
            continue

        if first_req:
            if wf_req:
                assert wf_req <= first_req, (wid, wf_req, first_req)
            else:
                assert False, (wid, "missing required_inputs for first tool", first_req)
        elif wf_req:
            union: set[str] = set()
            for tool in seq:
                union.update(required_args_for_tool(tool))
            assert wf_req <= union, (wid, wf_req, union)