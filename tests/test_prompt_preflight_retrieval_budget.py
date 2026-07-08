"""Prompt Preflight — progressive retrieval budget."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_broad_search_starts_at_metadata_discovery() -> None:
    plan = route_prompt("Find the source file for the contract")
    rb = plan["retrieval_budget"]
    assert rb["default_layer"] == "metadata_discovery"
    assert rb["deep_parse_requires_operator_selection"] is True
    assert rb["why_not_deep_read_all"]


def test_exact_id_allows_bounded_read_next() -> None:
    plan = route_prompt("Find the source file for the contract", has_exact_id=True)
    assert plan["retrieval_budget"]["recommended_next_layer"] == "bounded_read"


def test_budget_has_caps() -> None:
    plan = route_prompt("assemble context on the vendor")
    rb = plan["retrieval_budget"]
    assert isinstance(rb["max_candidates"], int) and rb["max_candidates"] > 0
    assert isinstance(rb["max_chars"], int) and rb["max_chars"] > 0
