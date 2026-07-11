"""Prompt Preflight — clause-scoped negation and modality-aware workflow scoring."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_mixed_clause_search_but_do_not_promote() -> None:
    plan = route_prompt("Search files but do not promote")
    auth = plan["authorization"]
    assert plan["recommended_workflow"] == "source_file_search"
    assert "promote" in auth["prohibitions"]
    assert auth["prompt_permission"]["promote"] is False
    assert auth["promotion_authorized"] is False


def test_mixed_clause_work_files_but_do_not_promote_anything() -> None:
    plan = route_prompt("Search my work files but do not promote anything")
    assert plan["recommended_workflow"] == "source_file_search"
    assert "promote" in plan["authorization"]["prohibitions"]


def test_quoted_promote_does_not_select_promotion_workflow() -> None:
    plan = route_prompt('The operator said "promote the artifact"')
    assert plan["recommended_workflow"] not in ("apply_canonical_promotion", "inspect_promotion_receipt")
    assert plan["recommended_workflow"] == "context_preflight"
    auth = plan["authorization"]
    assert auth["prompt_permission"]["promote"] is False
    assert auth["promotion_authorized"] is False
    assert auth["operation_modality"] == "imperative"


def test_capability_inquiry_promote_routes_to_discovery() -> None:
    plan = route_prompt("Can you promote decisions?")
    assert plan["recommended_workflow"] not in ("apply_canonical_promotion", "inspect_promotion_receipt")
    assert plan["recommended_workflow"] == "context_preflight"
    auth = plan["authorization"]
    assert auth["prompt_permission"]["promote"] is False
    assert auth["operation_modality"] == "capability_inquiry"


def test_hypothetical_promote_does_not_authorize_promotion() -> None:
    plan = route_prompt("What if we promoted this?")
    assert plan["recommended_workflow"] not in ("apply_canonical_promotion", "inspect_promotion_receipt")
    assert plan["recommended_workflow"] == "context_preflight"
    auth = plan["authorization"]
    assert auth["prompt_permission"]["promote"] is False
    assert auth["operation_modality"] == "hypothetical"


def test_imperative_promote_still_requests_promotion_permission() -> None:
    plan = route_prompt("Promote the approved artifact.")
    auth = plan["authorization"]
    assert plan["recommended_workflow"] == "apply_canonical_promotion"
    assert auth["prompt_permission"]["promote"] is True
    assert auth["promotion_authorized"] is False
    assert auth["currently_executable"] is False


def test_imperative_stage_still_authorizes_staging() -> None:
    plan = route_prompt("Stage this for review.")
    auth = plan["authorization"]
    assert plan["recommended_workflow"] == "stage_artifact_proposals"
    assert auth["prompt_permission"]["stage"] is True
    assert auth["staging_authorized"] is True
    assert auth["operation_modality"] == "imperative"


def test_promotion_receipt_contrast_clause_blocks_promotion() -> None:
    plan = route_prompt("Review the promotion receipt but do not promote")
    auth = plan["authorization"]
    assert "promote" in auth["prohibitions"]
    assert auth["prompt_permission"]["promote"] is False
    assert plan["recommended_workflow"] != "apply_canonical_promotion"


def test_unicode_quoted_promote_with_anaphora_prohibition_audit_row_21() -> None:
    plan = route_prompt(
        "The document says \u201cpromote the artifact,\u201d but do not perform that action."
    )
    auth = plan["authorization"]
    assert plan["recommended_workflow"] not in ("apply_canonical_promotion", "inspect_promotion_receipt")
    assert auth["prompt_permission"]["promote"] is False
    assert "promote" in auth["prohibitions"]


def test_quoted_promote_do_so_does_not_authorize() -> None:
    plan = route_prompt('The operator said "promote the artifact". Do so.')
    assert plan["recommended_workflow"] not in ("apply_canonical_promotion", "inspect_promotion_receipt")
    assert plan["authorization"]["prompt_permission"]["promote"] is False


def test_imperative_promote_do_so_authorizes() -> None:
    plan = route_prompt("Promote the artifact. Do so.")
    assert plan["recommended_workflow"] == "apply_canonical_promotion"
    assert plan["authorization"]["prompt_permission"]["promote"] is True


def test_stage_anaphora_prohibition_blocks_staging() -> None:
    plan = route_prompt("Stage this for review. Do not do that action.")
    auth = plan["authorization"]
    assert "stage" in auth["prohibitions"]
    assert auth["prompt_permission"]["stage"] is False
    assert plan["recommended_workflow"] != "stage_artifact_proposals"


def test_search_without_writing_audit_row_11() -> None:
    plan = route_prompt("Search without writing anything.")
    assert plan["recommended_workflow"] == "source_file_search"
    assert "write" in plan["authorization"]["prohibitions"]
    assert plan["authorization"]["prompt_permission"]["read"] is True


def test_do_not_promote_anything_audit_row_6() -> None:
    plan = route_prompt("Do not promote anything.")
    assert plan["recommended_workflow"] not in ("apply_canonical_promotion", "inspect_promotion_receipt")
    assert "promote" in plan["authorization"]["prohibitions"]
    assert plan["authorization"]["prompt_permission"]["promote"] is False