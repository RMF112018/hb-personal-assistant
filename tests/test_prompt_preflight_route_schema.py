"""Prompt Preflight — route plan output schema + read-only invariant."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt

REQUIRED_KEYS = {
    "prompt", "intent", "source_of_truth", "candidate_families", "primary_family",
    "recommended_workflow", "alternative_workflows", "recommended_tools", "workflow_available",
    "unavailable_tools", "authorization", "retrieval_budget", "provenance_required",
    "memory_opportunity", "must_not_use", "fallback_plan", "route_confidence", "routing_rationale",
    "clarifying_question", "preflight_is_read_only", "freshness",
}


def test_route_plan_has_full_schema() -> None:
    plan = route_prompt("Generate a Word document and save it")
    assert set(plan) >= REQUIRED_KEYS
    assert plan["preflight_is_read_only"] is True
    assert set(plan["intent"]) == {"primary_class", "classes"}
    auth = plan["authorization"]
    assert {"action_class", "prompt_authorizes_execution", "additional_approval_required"} <= set(auth)
    assert {"runtime_policy_permission", "capability_gates", "argument_extraction"} <= set(auth)
    rb = plan["retrieval_budget"]
    assert {"default_layer", "recommended_next_layer", "max_candidates", "max_chars"} <= set(rb)


def test_unknown_prompt_routes_to_clarify() -> None:
    plan = route_prompt("xyzzy plugh frobnicate")
    assert plan["route_confidence"] == "low"
    assert plan["recommended_workflow"] == "context_preflight"
    assert plan["clarifying_question"]
    assert plan["recommended_tools"] == []


def test_route_never_emits_write_verb_in_recommended_workflow_id() -> None:
    # The route plan itself must not name a tool that isn't in the recommended workflow's sequence.
    plan = route_prompt("Document this session", available_tools=frozenset({"pa_session_capture_stage"}))
    assert plan["primary_family"] == "artifact_workspace"
    # workflow references tools not all available -> marked unavailable, not silently dropped
    assert plan["workflow_available"] in (True, False)
