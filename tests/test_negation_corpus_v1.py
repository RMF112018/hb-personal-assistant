"""Negation corpus v1 — clause-scoped prohibition must not block unrelated reads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt

_CORPUS = Path(__file__).resolve().parent / "fixtures" / "negation_corpus_v1.json"


def _load_cases() -> list[dict]:
    return list(json.loads(_CORPUS.read_text(encoding="utf-8"))["cases"])


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_negation_corpus(case: dict) -> None:
    plan = route_prompt(case["prompt"])
    auth = plan["authorization"]

    if case.get("expect_workflow"):
        assert plan["recommended_workflow"] == case["expect_workflow"]

    if case.get("read_authorized") is True:
        assert auth["read_tool_calls_authorized"] is True

    if case.get("read_authorized") is False:
        assert auth["read_tool_calls_authorized"] is False

    for op in case.get("prohibited_operations_include") or []:
        assert op in (plan.get("prohibited_operations") or [])

    for op in case.get("allowed_operations_include") or []:
        assert op in (plan.get("allowed_operations") or [])

    for cap in case.get("prohibitions_include") or []:
        assert cap in auth.get("prohibitions", [])

    if case.get("must_not_block_reason"):
        assert auth.get("execution_blocked_reason") != case["must_not_block_reason"]