"""Prompt Preflight — authorization: reads self-authorize, writes need explicit operator go."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_read_self_authorizes() -> None:
    plan = route_prompt("What did we decide about the budget")
    auth = plan["authorization"]
    assert auth["action_class"] == "read"
    assert auth["prompt_authorizes_execution"] is True
    assert auth["additional_approval_required"] is False


def test_generated_file_write_needs_approval() -> None:
    plan = route_prompt("Generate a Word document and save it")
    auth = plan["authorization"]
    assert auth["action_class"] == "staged_write"
    # The prompt alone never authorizes the write to execute.
    assert auth["prompt_authorizes_execution"] is False
    assert auth["additional_approval_required"] is True
    assert "output_id" in plan["provenance_required"]
    assert "operator_approval_id" in plan["provenance_required"]


def test_canonical_promotion_needs_approval() -> None:
    plan = route_prompt("Promote the decision record to canonical memory")
    auth = plan["authorization"]
    assert auth["action_class"] == "canonical_promotion"
    assert auth["prompt_authorizes_execution"] is False
    assert auth["additional_approval_required"] is True


def test_low_confidence_write_yields_clarifying_route() -> None:
    # ambiguous archive-ish phrasing that doesn't match a trigger cleanly
    plan = route_prompt("archive that output")
    if plan["authorization"]["action_class"] in ("archive", "staged_write"):
        assert plan["route_confidence"] != "low" or plan["clarifying_question"]
    else:
        assert plan["route_confidence"] == "low"
        assert plan["clarifying_question"]


def test_extended_permission_dimensions_on_beyond_read_only_prompt() -> None:
    """F-011: prompt_permission and server_policy_permission expose index/deploy/execute_non_read."""
    plan = route_prompt("Do not execute tools beyond read-only analysis.")
    auth = plan["authorization"]
    for key in ("read", "stage", "write", "promote", "external_action", "execute_non_read", "index", "deploy"):
        assert key in auth["prompt_permission"]
        assert key in auth["server_policy_permission"]
    assert auth["prompt_permission"]["execute_non_read"] is False
    assert auth["prompt_permission"]["read"] is True
    assert auth["approval_status"] == "not_required"
    assert "execution_blocker_precedence" in auth
    assert auth["execution_blocker_precedence"].index("missing_arguments") < auth[
        "execution_blocker_precedence"
    ].index("approval_required")


def test_promotion_bundle_missing_only_approval_id_is_missing_arguments() -> None:
    """F-012 audit row 41: bundle present but operator_approval_id missing → missing_arguments."""
    plan = route_prompt("Apply promotion bundle `PROMOB-ABCDEF12`.")
    auth = plan["authorization"]
    assert plan["next_step"]["tool"] == "pa_artifact_promotion_apply"
    assert auth["missing_required_arguments"] == ["operator_approval_id"]
    assert auth["execution_blocked_reason"] == "missing_arguments"
    assert auth["approval_status"] == "required_unsatisfied"


def test_promotion_bundle_with_approval_id_blocked_until_satisfied() -> None:
    """F-012 audit row 42: both IDs present but server approval not satisfied → approval_required."""
    plan = route_prompt(
        "Apply promotion bundle `PROMOB-ABCDEF12` with operator approval `APPR-12345678`."
    )
    auth = plan["authorization"]
    assert auth["missing_required_arguments"] == []
    assert auth["execution_blocked_reason"] == "approval_required"
    assert auth["approval_status"] == "required_unsatisfied"
    assert auth["approval_required"] is True


def test_read_route_approval_status_not_required() -> None:
    plan = route_prompt("What did we decide about the budget")
    auth = plan["authorization"]
    assert auth["approval_status"] == "not_required"
    assert auth["approval_satisfied"] is False
