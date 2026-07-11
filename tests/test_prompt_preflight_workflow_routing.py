"""Prompt Preflight — workflow routing + every workflow trigger routes back to itself."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import (
    _extract_prohibitions,
    _norm,
    _rank_workflows,
    route_prompt,
)
from hb_assistant.obsidian_mcp.workflow_recipe_manifest import WORKFLOWS, workflow_record


def test_d1_capture_beats_incidental_retrieval_on_tie() -> None:
    # "document this session" (capture) tied with "open loops" (retrieval) — the intent-tier tie-break
    # must pick the capture workflow, not the alphabetically-first retrieval one.
    plan = route_prompt("document this session as decisions and open loops")
    assert plan["recommended_workflow"] == "document_session"
    assert plan["primary_family"] == "artifact_workspace"


def test_d2_create_decision_artifact_routes_to_artifact_workspace() -> None:
    plan = route_prompt("create a decision artifact for a temporary MCP test")
    assert plan["primary_family"] == "artifact_workspace"
    assert plan["intent"]["primary_class"] != "unknown"


def test_d3_delete_intent_flagged_destructive() -> None:
    plan = route_prompt("delete README.md from the vault")
    assert plan.get("destructive_intent") is True
    assert plan["authorization"]["action_class"] == "destructive"
    assert plan["authorization"]["prompt_authorizes_execution"] is False
    assert plan["recommended_tools"] == []
    assert plan["clarifying_question"]


def test_manifest_freshness_intent_routes_to_freshness_check() -> None:
    # "is the manifest current + report any drift" is freshness intent, not a plain lookup. The
    # "do not refresh" clause must forbid refresh (scoped `index` prohibition) without downgrading
    # the route to manifest_lookup.
    prompt = ("Check whether the Client Tool Operating Manifest is current and report any drift. "
              "Do not refresh it.")
    plan = route_prompt(prompt)
    assert plan["recommended_workflow"] == "manifest_freshness_check"
    assert plan["primary_family"] == "client_tool_manifest"
    assert plan["recommended_tools"] == [
        "pa_tool_manifest_freshness_check", "pa_tool_surface_freshness_check"
    ]
    # negation preserved: refresh forbidden, and no refresh/promote tool is recommended.
    assert "index" in _extract_prohibitions(_norm(prompt))
    assert not any("refresh" in t or "promote" in t for t in plan["recommended_tools"])


def test_manifest_lookup_and_review_plan_are_not_stolen_by_freshness() -> None:
    # The added freshness vocabulary must not cannibalise the sibling manifest workflows.
    assert route_prompt("show me the tool operating manifest")["recommended_workflow"] == "manifest_lookup"
    review = route_prompt("should I refresh the manifest? give me a review manifest drift plan")
    assert review["recommended_workflow"] == "manifest_review_plan"


def test_every_workflow_trigger_phrase_ranks_its_own_workflow() -> None:
    # Each trigger phrase must at least surface its owning workflow in the ranked candidates.
    for wf in WORKFLOWS:
        for phrase in wf["trigger_phrases"]:
            ranked = _rank_workflows(_norm(phrase))
            ids = [w["workflow_id"] for _, w in ranked]
            assert wf["workflow_id"] in ids, (wf["workflow_id"], phrase)


def test_all_workflows_reference_valid_families() -> None:
    from hb_assistant.obsidian_mcp.tool_family_manifest import FAMILY_IDS
    for wf in WORKFLOWS:
        assert wf["family_id"] in FAMILY_IDS, wf["workflow_id"]


def test_generation_workflows_reference_real_output_tools() -> None:
    for wid in ("generate_docx_output", "generate_pdf_output", "generate_zip_package"):
        wf = workflow_record(wid)
        assert wf is not None
        assert "pa_output_stage" in wf["tool_sequence"]
        assert "pa_output_commit" in wf["tool_sequence"]


def test_workflow_ids_unique() -> None:
    ids = [w["workflow_id"] for w in WORKFLOWS]
    assert len(ids) == len(set(ids))
