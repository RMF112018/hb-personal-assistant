"""PR-32 — workflow sequence defaults and argument population usability fixes."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_feedback_review_lists_before_get() -> None:
    plan = route_prompt("Show me feedback recommendations")
    assert plan["recommended_workflow"] == "feedback_review"
    assert plan["recommended_tools"][:2] == [
        "assistant_list_feedback",
        "assistant_get_feedback",
    ]
    assert plan["next_step"]["tool"] == "assistant_list_feedback"
    assert plan["authorization"]["currently_executable"] is True


def test_action_stage_review_lists_before_get() -> None:
    plan = route_prompt("Review staged actions")
    assert plan["recommended_workflow"] == "action_stage_review"
    assert plan["recommended_tools"][:2] == [
        "assistant_list_action_stages",
        "assistant_get_action_stage",
    ]
    assert plan["next_step"]["tool"] == "assistant_list_action_stages"
    assert plan["authorization"]["currently_executable"] is True


def test_output_id_routes_to_metadata_workflow() -> None:
    plan = route_prompt("Get metadata for OUTPUT-20260711-001")
    assert plan["recommended_workflow"] == "inspect_generated_output_metadata"
    assert plan["next_step"]["tool"] == "pa_output_metadata"
    assert plan["next_step"]["arguments"]["output_id"] == "OUTPUT-20260711-001"
    assert plan["authorization"]["currently_executable"] is True


def test_promotion_receipt_id_populates_getter() -> None:
    plan = route_prompt("Inspect promotion receipt PROMO-20260711-001")
    assert plan["recommended_workflow"] == "inspect_promotion_receipt"
    assert plan["next_step"]["tool"] == "pa_artifact_promotion_receipt_get"
    assert plan["next_step"]["arguments"]["promotion_receipt_id"] == "PROMO-20260711-001"
    assert plan["authorization"]["currently_executable"] is True


def test_output_receipt_with_output_id_uses_metadata_getter() -> None:
    plan = route_prompt("Show output receipt OUTPUT-20260711-001")
    assert plan["recommended_workflow"] == "retrieve_generated_output_receipt"
    assert plan["next_step"]["tool"] == "pa_output_metadata"
    assert plan["next_step"]["arguments"]["output_id"] == "OUTPUT-20260711-001"
    assert plan["authorization"]["currently_executable"] is True


def test_csv_export_extracts_title_and_file_type() -> None:
    plan = route_prompt("Export to CSV titled Budget Summary")
    assert plan["recommended_workflow"] == "generate_csv_output"
    args = plan["next_step"]["arguments"]
    assert args["title"] == "Budget Summary"
    assert args["file_type"] == "csv"
    assert args["content_mode"] == "csv_text"
    assert "content_text" not in args
    assert plan["authorization"]["currently_executable"] is True


def test_docx_export_extracts_title_and_format() -> None:
    plan = route_prompt("Generate a word doc called Project Closeout")
    assert plan["recommended_workflow"] == "generate_docx_output"
    args = plan["next_step"]["arguments"]
    assert args["title"] == "Project Closeout"
    assert args["file_type"] == "docx"
    assert args["content_mode"] == "docx_from_markdown_or_text"


def test_output_metadata_lists_before_get_without_id() -> None:
    plan = route_prompt("Show output metadata")
    assert plan["recommended_workflow"] == "inspect_generated_output_metadata"
    assert plan["next_step"]["tool"] == "pa_output_list"
    assert plan["authorization"]["currently_executable"] is True