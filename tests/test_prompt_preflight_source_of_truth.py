"""Prompt Preflight — source-of-truth classification keeps surfaces distinct."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt


def test_generated_file_source_is_outputs_not_vault() -> None:
    plan = route_prompt("make a markdown file")
    sot = plan["source_of_truth"].lower()
    assert "outputs" in sot
    assert "vault" in sot  # explicitly says NOT the vault


def test_decision_source_is_canonical_records() -> None:
    plan = route_prompt("what did we decide about the change order")
    assert "canonical" in plan["source_of_truth"].lower()


def test_source_search_source_is_indexed_files() -> None:
    plan = route_prompt("find the file about the RFP")
    assert "source file" in plan["source_of_truth"].lower()


def test_markdown_file_not_confused_with_vault_note() -> None:
    plan = route_prompt("make a markdown file")
    joined = " ".join(plan["must_not_use"]).lower()
    assert "vault note" in joined or "obsidian" in joined
