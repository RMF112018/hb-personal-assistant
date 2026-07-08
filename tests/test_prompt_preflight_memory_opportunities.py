"""Prompt Preflight — memory-opportunity detection never auto-stages."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_durable_fact_flags_memory_opportunity() -> None:
    plan = route_prompt("Just so you know, going forward we always use net-30 terms")
    mem = plan["memory_opportunity"]
    assert mem["detected"] is True
    assert mem["suggested_workflow"] == "document_session"
    assert mem["must_not_auto_stage"] is True


def test_plain_retrieval_has_no_memory_opportunity() -> None:
    plan = route_prompt("find the source file for the contract")
    assert plan["memory_opportunity"]["detected"] is False


def test_capture_intent_does_not_double_flag() -> None:
    # An explicit "document this session" already routes to capture; don't also flag it as an opportunity.
    plan = route_prompt("document this session and remember this")
    assert plan["primary_family"] == "artifact_workspace"
    assert plan["memory_opportunity"]["detected"] is False


def test_memory_opportunity_never_writes() -> None:
    plan = route_prompt("remember that the budget was approved")
    assert plan["memory_opportunity"]["must_not_auto_stage"] is True
    assert plan["preflight_is_read_only"] is True
