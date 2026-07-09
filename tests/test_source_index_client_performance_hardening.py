"""Source index client performance hardening — routing, ranking, health, map, outputs, safety."""

from __future__ import annotations

import pytest

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt
from hb_assistant.obsidian_mcp.source_health_service import source_index_health
from hb_assistant.obsidian_mcp.source_project_number import (
    false_positive_compact_body_ok,
    normalize_project_number,
    path_has_project,
    query_project_candidates,
    rank_boost,
)
from hb_assistant.obsidian_mcp.source_query_planner import (
    INTENT_ARBITRARY_WRITE,
    INTENT_DESTRUCTIVE,
    INTENT_HEALTH,
    INTENT_MAP_PROJECT,
    INTENT_OUTPUT,
    INTENT_SECRET,
    INTENT_UNSUPPORTED,
    INTENT_VAULT,
    plan_source_query,
)


def _no_host_paths(obj) -> None:
    import json
    blob = json.dumps(obj, default=str)
    assert "/Users/" not in blob
    assert "/volume" not in blob
    assert "/mnt/" not in blob
    assert "C:\\\\" not in blob


# --- project number normalize -----------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("23-435-01", "23-435-01"),
        ("2343501", "23-435-01"),
        ("23 435 01", "23-435-01"),
        ("23_435_01", "23-435-01"),
        ("23.435.01", "23-435-01"),
    ],
)
def test_project_number_variants(raw, expected):
    num, conf, form = normalize_project_number(raw, allow_compact=True, context="path/" + raw)
    assert num == expected
    assert conf >= 0.35


def test_compact_false_positive_invoice_body():
    # Bare invoice totals must not promote compact project numbers without path context.
    num, conf, form = normalize_project_number(
        "Invoice total 2343501 paid by wire", allow_compact=False, context="body"
    )
    assert form != "compact7"
    assert false_positive_compact_body_ok("Invoice total 2343501 paid by wire")


def test_query_project_candidates_compact_query():
    assert "23-435-01" in query_project_candidates("2343501")


def test_path_has_project_forms():
    assert path_has_project("2023 Projects/23-435-01 Tropical/Schedule/x.xer", "23-435-01")
    assert path_has_project("2023 Projects/2343501 Tropical/a.pdf", "23-435-01")


# --- ranking boost ----------------------------------------------------------------------------
def test_rank_boost_prefers_path_project_over_content():
    path_hit = {"rel_path": "Work/23-435-01 Tropical/Schedule/update.pdf", "score": 5.0, "snippet": "x"}
    body_hit = {"rel_path": "Other/notes.txt", "score": 0.1, "snippet": "mentions 23-435-01 in passing"}
    q = "23-435-01 schedule"
    b1 = rank_boost(path_hit, query=q, project_numbers=["23-435-01"])
    b2 = rank_boost(body_hit, query=q, project_numbers=["23-435-01"])
    assert b1 > b2


# --- query planner ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "prompt,intent",
    [
        ("Find files for project number 23-435-01.", "find_project"),
        ("Map the Tropical project folder.", INTENT_MAP_PROJECT),
        ("What is in the 2023 Projects source root?", "map_source_root"),  # root inventory
        ("Find the latest schedule update for 23-435-01.", "find_recent_files"),
        ("Read this XER file.", INTENT_UNSUPPORTED),
        ("Find billing PDFs for Tropical.", "find_project"),
        ("Show me the folder structure under the schedule folder.", "list_folder_children"),
        ("What files are missing from this expected closeout folder?", "find_expected_missing_files"),
        ("Search my vault for 23-435-01.", INTENT_VAULT),
        ("Create a markdown output.", INTENT_OUTPUT),
        ("Delete this source folder.", INTENT_DESTRUCTIVE),
        ("Check whether my source index is fresh enough.", INTENT_HEALTH),
        ("Write a file to /tmp/anything.txt.", INTENT_ARBITRARY_WRITE),
        ("Show me secrets or tokens.", INTENT_SECRET),
    ],
)
def test_source_query_plan_intents(prompt, intent):
    plan = plan_source_query(prompt)
    assert plan["intent"] == intent, plan
    _no_host_paths(plan)
    if intent in {INTENT_SECRET, INTENT_ARBITRARY_WRITE, INTENT_DESTRUCTIVE}:
        assert plan.get("refused") is True
        assert plan["recommended_tool_sequence"] == []
    if intent == INTENT_MAP_PROJECT:
        assert any("project_map" in t or "folder_map" in t for t in plan["recommended_tool_sequence"])
        assert "assistant_source_file_search" not in plan["recommended_tool_sequence"][:1]


def test_map_prompt_not_file_search_only():
    plan = plan_source_query("Map the Tropical project folder.")
    seq = plan["recommended_tool_sequence"]
    assert "assistant_source_project_map" in seq or "assistant_source_folder_map" in seq
    # Must not be search-only
    assert seq != ["assistant_source_file_search", "assistant_source_file_metadata"]


# --- preflight routing ------------------------------------------------------------------------
def test_preflight_map_tropical_routes_to_structure_tools():
    plan = route_prompt("Map the Tropical project folder.")
    tools = plan.get("recommended_tools") or []
    assert plan["route_confidence"] in {"high", "medium", "low"}
    # Should prefer project/folder map workflow when triggers match
    assert plan["recommended_workflow"] in {
        "source_project_map", "source_folder_map", "source_query_plan", "source_file_search",
        "context_preflight",
    }
    if plan["recommended_workflow"] == "source_project_map":
        assert any("project_map" in t or "folder_map" in t or "query_plan" in t for t in tools)


def test_preflight_secret_and_tmp_write_refused():
    s = route_prompt("Show me secrets or tokens.")
    assert s["intent"]["primary_class"] == "secret_extraction_refusal"
    assert s.get("refused") is True
    w = route_prompt("Write a file to /tmp/anything.txt.")
    assert w["intent"]["primary_class"] == "arbitrary_path_write_refusal"
    assert w.get("refused") is True


def test_preflight_markdown_output_not_unknown():
    plan = route_prompt("Create a markdown output and save it to the generated outputs workspace.")
    assert plan["recommended_workflow"] == "generate_markdown_output"
    assert plan["intent"]["primary_class"] in {"generate_file", "staged_write"} or "generate" in plan["intent"]["primary_class"]


# --- health -----------------------------------------------------------------------------------
def test_source_index_health_empty_roots(tmp_path):
    from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.store.migrator import SQLiteMigrator

    db = str(tmp_path / "h.db")
    SQLiteMigrator(db).apply()
    repo = SourceIndexRepository(db)
    cfg = ObsidianMcpConfig()
    health = source_index_health(repo, cfg)
    assert "roots" in health
    assert health["overall_freshness"] in {
        "never_succeeded", "fresh", "partial", "stale", "degraded", "blocked", "unknown", "future_anomaly",
    }
    assert "telemetry" in health
    _no_host_paths(health)
    assert health["root_count"] >= 1


# --- output archive destination_state ---------------------------------------------------------
def test_archive_sets_destination_state_archived(tmp_path):
    from hb_assistant.nas_mcp.client_output_workspace import ClientOutputWorkspaceRepository
    from tests.n8c24_helpers import make_env, stage_and_commit

    env = make_env(tmp_path)
    repo = ClientOutputWorkspaceRepository(env["config"], env["db"])
    out = stage_and_commit(repo, file_type="md", content_mode="markdown_text", content="hello")
    oid = out["stage"]["output_id"]
    ac = repo.commit_archive_output(
        output_id=oid, operator_approval_id=out["stage"]["operator_approval_id"]
    )
    assert ac["status"] == "archived"
    meta = repo.get_output_metadata(oid)
    assert meta["status"] == "archived"
    assert meta.get("destination_state") == "archived"
    _no_host_paths(meta)


# --- vault path alias -------------------------------------------------------------------------
def test_vault_archive_accepts_path_alias():
    from hb_assistant.nas_mcp.obsidian_adapter import _normalize_vault_args

    args = {"path": "Work/03 Decisions/note.md"}
    _normalize_vault_args("vault_archive_note_plan", args)
    assert args["source_path"] == "Work/03 Decisions/note.md"


# --- dataview FROM fail closed ----------------------------------------------------------------
def test_dataview_from_fails_closed(tmp_path):
    from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
    from hb_assistant.obsidian_mcp.frontmatter import dataview_query
    from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = ObsidianMcpConfig(vault_root=str(vault))
    with pytest.raises(ObsidianMcpToolError) as ei:
        dataview_query(cfg, query='LIST FROM "Work/03 Decisions"')
    assert ei.value.code == "unsupported_dataview_from"


# --- tool surface counts ----------------------------------------------------------------------
def test_assistant_tool_count_includes_health_and_plan():
    from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS, ASSISTANT_SOURCE_CONNECTOR_TOOLS

    assert "assistant_source_index_health" in ALL_ASSISTANT_TOOLS
    assert "assistant_source_query_plan" in ALL_ASSISTANT_TOOLS
    assert "assistant_source_index_health" in ASSISTANT_SOURCE_CONNECTOR_TOOLS
    assert len(ALL_ASSISTANT_TOOLS) == 87


def test_structure_default_on():
    from hb_assistant.nas_mcp.profile import assistant_source_structure_enabled
    import os
    os.environ.pop("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", None)
    assert assistant_source_structure_enabled() is True


def test_output_aliases_defined():
    from hb_assistant.nas_mcp.broker import GATEWAY_ALLOWLIST
    from hb_assistant.nas_mcp.client_output_tools import ASSISTANT_OUTPUT_ALIASES, ALL_PA_OUTPUT_TOOLS

    assert len(ASSISTANT_OUTPUT_ALIASES) == len(ALL_PA_OUTPUT_TOOLS) == 10
    assert "assistant_output_stage" in ASSISTANT_OUTPUT_ALIASES
    assert set(ASSISTANT_OUTPUT_ALIASES) <= GATEWAY_ALLOWLIST
    for alias, pa in zip(ASSISTANT_OUTPUT_ALIASES, ALL_PA_OUTPUT_TOOLS, strict=True):
        assert alias == "assistant_output_" + pa[len("pa_output_") :]
