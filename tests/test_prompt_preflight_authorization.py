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
