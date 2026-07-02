"""Tests for schedule graph LLM suggestion validation (Phase 20, report-only)."""

from __future__ import annotations

import json

from hb_assistant.obsidian_mcp.schedule_note_graph import ScheduleGraphCandidate
from hb_assistant.obsidian_mcp.schedule_note_graph_llm_validation import (
    build_suggestion_prompt,
    validate_llm_suggestions,
)


def _cand(key: str = "abc") -> ScheduleGraphCandidate:
    return ScheduleGraphCandidate(
        candidate_key=key,
        source_note="Work/HB Personal Assistant/Schedule Review/Projects/tropical/a.md",
        target_note="Work/HB Personal Assistant/Schedule Review/Projects/tropical/b.md",
        relationship_type="same_project_schedule_note",
        confidence=0.9,
        basis=("same_project_key",),
        recommended=True,
        requires_human_review=True,
        pm_safe_label="Related schedule note",
    )


def test_validate_accepts_known_keys() -> None:
    raw = json.dumps({"selected_keys": ["abc"], "rationale": "Same project pair."})
    result = validate_llm_suggestions(raw, [_cand()])
    assert result["passed"] is True
    assert result["selected_keys"] == ["abc"]
    assert result["report_only"] is True


def test_validate_rejects_unknown_key() -> None:
    raw = json.dumps({"selected_keys": ["missing"], "rationale": "n/a"})
    result = validate_llm_suggestions(raw, [_cand()])
    assert result["passed"] is False
    assert "unknown_candidate_key" in result["violations"][0]


def test_validate_rejects_path_leak_in_rationale() -> None:
    raw = json.dumps({"selected_keys": [], "rationale": "See /Users/bobbyfetting/secret"})
    result = validate_llm_suggestions(raw, [_cand()])
    assert result["passed"] is False
    assert "forbidden_path_leak" in result["violations"]


def test_build_suggestion_prompt_uses_vault_relative_paths() -> None:
    prompt = build_suggestion_prompt([_cand()])
    assert "Work/HB Personal Assistant/Schedule Review" in prompt
    assert "/Users/" not in prompt
