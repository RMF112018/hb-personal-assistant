"""Central typed-ID parser — corpus-driven extraction and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.prompt_id_parser import (
    ValidationState,
    extract_asserted_typed_ids,
    extract_validated_id,
    parse_prompt_ids,
    validate_tool_argument_ids,
)
from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt

_CORPUS = Path(__file__).resolve().parent / "fixtures" / "typed_id_corpus_v1.json"


def _load_corpus() -> list[dict]:
    data = json.loads(_CORPUS.read_text(encoding="utf-8"))
    return list(data["cases"])


@pytest.mark.parametrize("case", _load_corpus(), ids=lambda c: c["id"])
def test_typed_id_corpus(case: dict) -> None:
    prompt = case["prompt"]
    arg = case.get("arg")
    expect = case.get("expect")
    if arg:
        assert extract_validated_id(prompt, arg) == expect
    if case.get("asserted_empty"):
        assert extract_asserted_typed_ids(prompt) == []


def test_promob_hyphenated_not_truncated() -> None:
    """Regression: PROMOB-20260711-001 must not truncate to PROMOB-20260711."""
    val = extract_validated_id("Apply PROMOB-20260711-001 now", "promotion_bundle_id")
    assert val == "PROMOB-20260711-001"


def test_promob_route_populates_apply_args() -> None:
    plan = route_prompt(
        "Promote bundle `PROMOB-20260711-001` using approval `APPR-12345678`."
    )
    assert plan["recommended_workflow"] == "apply_canonical_promotion"
    args = plan["next_step"]["arguments"]
    assert args.get("promotion_bundle_id") == "PROMOB-20260711-001"
    assert args.get("operator_approval_id") == "APPR-12345678"


def test_parse_detects_partial_promob() -> None:
    result = parse_prompt_ids("Apply PROMOB-20260711 only")
    promob = [p for p in result.ids if p.value.upper().startswith("PROMOB-")]
    assert promob
    assert promob[0].validation_state == ValidationState.PARTIAL_MATCH


def test_validate_tool_argument_ids_rejects_partial() -> None:
    errors = validate_tool_argument_ids(
        "pa_artifact_promotion_apply",
        {"promotion_bundle_id": "PROMOB-20260711"},
    )
    assert "promotion_bundle_id" in errors


def test_multiple_distinct_decision_ids_conflict() -> None:
    result = parse_prompt_ids(
        "Retrieve DEC-20260708-7847F4 and DEC-20260708-A08367"
    )
    assert len(result.conflicts) >= 2


def test_slug_decision_id_preserved() -> None:
    val = extract_validated_id("Get decision decision_abc12345", "decision_id")
    assert val == "decision_abc12345"