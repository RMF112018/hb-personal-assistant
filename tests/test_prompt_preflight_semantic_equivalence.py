"""Audit regression matrix (50 prompts) and semantic equivalence groups."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt  # noqa: E402
from route_proof_lib import evaluate_route_expectations, route_actual  # noqa: E402

_MATRIX_PATH = ROOT / "scripts" / "audit-route-regression-matrix.json"
_AUDIT_CASES: list[dict] = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))

EQUIVALENCE_GROUPS: list[dict] = [
    {
        "workflow": "source_file_search",
        "prompts": [
            "Search my work files.",
            "Search work files for budget",
            "Look in the nas for contract",
            "Find files on the nas",
            "Search original files for specs",
            "Look through the files in Work.",
            "Search my Work source files.",
        ],
    },
    {
        "workflow": "vault_note_search",
        "prompts": [
            "Search the vault for meeting notes.",
            "Find notes in obsidian",
            "Search obsidian for meeting notes",
            "Find my project notes.",
        ],
    },
    {
        "workflow": "stage_artifact_proposals",
        "prompts": [
            "Stage this for review.",
            "Submit for review.",
            "Queue for review.",
            "Put this up for review.",
        ],
    },
]


def test_audit_matrix_has_fifty_cases() -> None:
    assert len(_AUDIT_CASES) == 50


@pytest.mark.parametrize("case", _AUDIT_CASES, ids=[c["id"] for c in _AUDIT_CASES])
def test_audit_regression_matrix(case: dict) -> None:
    plan = route_prompt(case["prompt"])
    actual = route_actual(plan)
    mismatches = evaluate_route_expectations(case["expected"], actual)
    assert mismatches == [], (case["id"], mismatches, actual)


@pytest.mark.parametrize("group", EQUIVALENCE_GROUPS, ids=[g["workflow"] for g in EQUIVALENCE_GROUPS])
def test_semantic_equivalence_group_routes_consistently(group: dict) -> None:
    expected_wf = group["workflow"]
    for prompt in group["prompts"]:
        plan = route_prompt(prompt)
        assert plan["recommended_workflow"] == expected_wf, (prompt, plan["recommended_workflow"])