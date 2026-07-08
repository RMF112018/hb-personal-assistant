"""Prompt Preflight — fallback plans never fall back unsafely from controlled writes."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_generated_file_write_blocks_unsafe_fallback() -> None:
    plan = route_prompt("Generate a Word document and save it")
    fp = plan["fallback_plan"]
    assert fp["unsafe_fallback_blocked"] is True
    # never suggests the legacy scratch writer
    rules = " ".join(fp["rules"]).lower()
    assert "hb_output_write_file" not in " ".join(plan["recommended_tools"]).lower()
    assert "hb_output_write_file" in rules or "never" in rules or rules == ""


def test_read_may_have_safe_fallback() -> None:
    plan = route_prompt("find the source file for the contract")
    assert plan["fallback_plan"]["unsafe_fallback_blocked"] is False


def test_canonical_promotion_never_falls_back_to_raw_write() -> None:
    plan = route_prompt("apply promotion to canonical memory")
    fp = plan["fallback_plan"]
    assert fp["unsafe_fallback_blocked"] is True
    assert "raw vault write" in " ".join(fp["rules"]).lower() or fp["rules"] == []
