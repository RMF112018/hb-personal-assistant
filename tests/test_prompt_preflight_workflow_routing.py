"""Prompt Preflight — workflow routing + every workflow trigger routes back to itself."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import _norm, _rank_workflows
from hb_assistant.obsidian_mcp.workflow_recipe_manifest import WORKFLOWS, workflow_record


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
