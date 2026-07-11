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


def test_typed_decision_id_show_me_routes_to_getter() -> None:
    """Audit row 25: typed DEC- ID with show-me phrasing must not fall through to context_preflight."""
    plan = route_prompt("Show me decision `DEC-20260708-7847F4`")
    assert plan["recommended_workflow"] == "canonical_decision_retrieval"
    assert plan["next_step"]["tool"] == "assistant_get_decision"
    assert plan["next_step"]["arguments"]["decision_id"] == "DEC-20260708-7847F4"
    assert plan["authorization"]["currently_executable"] is True
    assert any("exact_id_getter" in c for c in plan.get("constraints") or [])


def test_typed_preference_id_routes_to_getter() -> None:
    """Audit row 28."""
    plan = route_prompt("Retrieve the preference `PREF-20260708-2D3D8D`")
    assert plan["recommended_workflow"] == "canonical_preference_retrieval"
    assert plan["next_step"]["tool"] == "assistant_get_preference"
    assert plan["next_step"]["arguments"]["preference_id"] == "PREF-20260708-2D3D8D"
    assert plan["authorization"]["currently_executable"] is True


def test_typed_open_loop_id_routes_to_getter() -> None:
    """Audit row 30."""
    plan = route_prompt("Retrieve the open loop `LOOP-20260708-B21D38`")
    assert plan["recommended_workflow"] == "canonical_open_loop_retrieval"
    assert plan["next_step"]["tool"] == "assistant_get_open_loop"
    assert plan["next_step"]["arguments"]["open_loop_id"] == "LOOP-20260708-B21D38"
    assert plan["authorization"]["currently_executable"] is True


def test_multiple_typed_decision_ids_produce_ambiguity_not_silent_pick() -> None:
    """Audit row 47: never silently pick the first of multiple DEC- IDs."""
    plan = route_prompt(
        "Retrieve the decision `DEC-20260708-7847F4` and `DEC-20260708-A08367`"
    )
    assert plan["recommended_workflow"] == "context_preflight"
    assert plan["next_step"] is None
    assert plan.get("conflicting_ids") == [
        "DEC-20260708-7847F4",
        "DEC-20260708-A08367",
    ]
    assert plan["clarifying_question"] is not None
    assert plan["authorization"]["currently_executable"] is False


def test_example_typed_id_is_not_retrieval_target() -> None:
    """Audit row 48: quoted for-example IDs must not route to a getter."""
    plan = route_prompt(
        'For example, "DEC-20260708-7847F4" is a decision ID. Explain the format.'
    )
    assert plan["recommended_workflow"] == "context_preflight"
    assert plan["next_step"] is None
    assert "conflicting_ids" not in plan


def test_look_through_files_routes_source_search() -> None:
    """Audit row 14: look-through phrasing is search-equivalent."""
    plan = route_prompt("Look through the files in Work.")
    assert plan["recommended_workflow"] == "source_file_search"
    assert plan["next_step"]["tool"] == "assistant_source_file_search"
    assert plan["next_step"]["arguments"]["query"] == "files in work"
    assert plan["authorization"]["currently_executable"] is True


def test_documents_under_root_routes_file_search_not_root_map() -> None:
    """Audit row 15: document retrieval beats root-map when both cues appear."""
    plan = route_prompt("Find documents stored under my Work source root.")
    assert plan["recommended_workflow"] == "source_file_search"
    assert plan["next_step"]["tool"] == "assistant_source_file_search"
    assert plan["authorization"]["currently_executable"] is True


def test_original_pdf_contract_routes_source_file_search() -> None:
    """Audit row 33: original PDF/contract cues imply indexed source file search."""
    plan = route_prompt("Find the original PDF contract.")
    assert plan["recommended_workflow"] == "source_file_search"
    assert plan["next_step"]["tool"] == "assistant_source_file_search"
    assert "contract" in plan["next_step"]["arguments"]["query"].lower()
    assert plan["authorization"]["currently_executable"] is True


def test_source_map_question_routes_root_map() -> None:
    """Audit row 38: source-map questions route to structure/root-map workflow."""
    plan = route_prompt("What does my source map say about Work?")
    assert plan["recommended_workflow"] == "source_root_map"
    assert plan["authorization"]["read_tool_calls_authorized"] is True


def test_promotion_receipt_noun_only_does_not_route_inspect() -> None:
    """Audit row 12: bare receipt noun in a prohibition must not create inspect intent."""
    plan = route_prompt('Do not delete anything named "promotion receipt."')
    assert plan["recommended_workflow"] == "context_preflight"
    assert plan["recommended_workflow"] != "inspect_promotion_receipt"
    assert plan["next_step"] is None


def test_search_intent_wins_over_incidental_typed_id_mention() -> None:
    """Audit row 50: file search must not be overridden by an unrelated ID mention."""
    plan = route_prompt(
        "The report mentions `DEC-20260708-7847F4`, but search my work files for the contract."
    )
    assert plan["recommended_workflow"] == "source_file_search"
    assert plan["next_step"]["tool"] == "assistant_source_file_search"
    assert plan["next_step"]["arguments"]["query"] == "the contract"