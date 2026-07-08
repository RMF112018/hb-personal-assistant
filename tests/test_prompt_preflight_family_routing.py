"""Prompt Preflight — family routing + tool→family totality."""

from __future__ import annotations

import pytest

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt
from hb_assistant.obsidian_mcp.tool_family_manifest import FAMILIES, FAMILY_IDS, family_for_tool

CASES = [
    ("Generate a Word doc and save it", "client_output_workspace"),
    ("Make a spreadsheet from this data", "client_output_workspace"),
    ("Make a PDF report", "client_output_workspace"),
    ("Bundle these files into a zip", "client_output_workspace"),
    ("Document this session", "artifact_workspace"),
    ("Promote the decision record to canonical memory", "canonical_promotion"),
    ("Find the source file for the contract", "assistant_source_connector"),
    ("What did we decide about the schedule", "assistant_decision_memory"),
    ("Show generated files", "output_receipts_manifests"),
    ("Is the server up", "status_health"),
]


@pytest.mark.parametrize("prompt,expected_family", CASES)
def test_family_routing(prompt: str, expected_family: str) -> None:
    plan = route_prompt(prompt)
    assert plan["primary_family"] == expected_family, (prompt, plan["primary_family"])
    assert expected_family in plan["candidate_families"]


def test_exactly_24_families_all_unique() -> None:
    assert len(FAMILIES) == 24
    assert len(FAMILY_IDS) == 24


def test_generated_file_never_routes_to_vault_or_canonical() -> None:
    for prompt in ("save this as docx", "export to excel", "make a pdf", "save as html"):
        plan = route_prompt(prompt)
        assert plan["primary_family"] == "client_output_workspace"
        assert "canonical_promotion" not in plan["candidate_families"]
        joined = " ".join(plan["must_not_use"]).lower()
        assert "vault" in joined and "canonical" in joined


def test_every_known_tool_maps_to_a_valid_family() -> None:
    for name in ("pa_output_stage", "pa_output_list", "hb_output_write_file", "pa_prompt_route",
                 "pa_artifact_promotion_apply", "assistant_get_decision", "hb_db_select", "raw_sql",
                 "ai_outputs_card_upsert", "hb_mcp_status", "unknown_future_tool"):
        assert family_for_tool(name) in FAMILY_IDS


def test_legacy_output_maps_to_legacy_family() -> None:
    assert family_for_tool("hb_output_write_file") == "legacy_low_level"
    assert family_for_tool("raw_sql") == "blocked_deprecated"
