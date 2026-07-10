"""Prompt Preflight — schema-aware natural-language argument extraction."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_work_files_search_extracts_query_and_is_executable() -> None:
    plan = route_prompt("Search my work files.")
    assert plan["recommended_workflow"] == "source_file_search"
    assert plan["next_step"]["tool"] == "assistant_source_file_search"
    assert plan["next_step"]["arguments"].get("query") == "work files"
    auth = plan["authorization"]
    assert auth["currently_executable"] is True
    assert auth["execution_blocked_reason"] is None
    assert "query" in auth["argument_extraction"]["populated"]


def test_work_files_search_for_topic_extracts_query() -> None:
    plan = route_prompt("Search my work files for budget")
    assert plan["next_step"]["arguments"].get("query") == "budget"
    assert plan["authorization"]["currently_executable"] is True


def test_vault_search_extracts_query() -> None:
    plan = route_prompt("Search the vault for meeting notes.")
    assert plan["recommended_workflow"] == "vault_note_search"
    assert plan["next_step"]["tool"] == "assistant_search_sources"
    assert plan["next_step"]["arguments"].get("query") == "meeting notes"
    assert plan["authorization"]["currently_executable"] is True


def test_exact_decision_id_selects_getter_with_args() -> None:
    plan = route_prompt("Get decision decision_abc12345")
    assert plan["recommended_workflow"] == "canonical_decision_retrieval"
    assert plan["next_step"]["tool"] == "assistant_get_decision"
    assert plan["next_step"]["arguments"].get("decision_id", "").lower() == "decision_abc12345"
    assert plan["authorization"]["currently_executable"] is True
    assert any("exact_id_getter" in c for c in plan.get("constraints") or [])


def test_retrieve_canonical_decision_populates_id_not_bare_noun() -> None:
    plan = route_prompt("Retrieve the canonical decision decision_abc12345 from memory.")
    get_step = plan["next_step"]
    assert get_step["tool"] == "assistant_get_decision"
    assert get_step["arguments"]["decision_id"].lower() == "decision_abc12345"


def test_malformed_id_stays_missing_arguments() -> None:
    plan = route_prompt("Get decision not-a-real-id")
    assert plan["next_step"]["tool"] == "assistant_list_decisions"
    assert plan["authorization"]["currently_executable"] is True
    get_step = next(s for s in plan["additional_steps"] if s["tool"] == "assistant_get_decision")
    assert get_step["arguments"] == {}
    assert "decision_id" in get_step["missing_required_arguments"]


def test_stage_for_review_still_missing_session_bundle_args() -> None:
    plan = route_prompt("Stage this for review.")
    assert plan["recommended_workflow"] == "stage_artifact_proposals"
    assert plan["authorization"]["currently_executable"] is False
    assert plan["authorization"]["execution_blocked_reason"] == "missing_arguments"