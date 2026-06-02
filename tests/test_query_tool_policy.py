"""Phase 08A Prompt 06 — SQLite query-tool allowlist + policy.

Proves the allowlist, seed, and contract agree; the policy validates with the
no-arbitrary/no-mutation-SQL + source-refs/review-tier posture; every allowlisted
tool maps to a family slot; and a non-allowlisted (model-authored) tool name is
rejected before any DB access.
"""

from __future__ import annotations

import pytest

from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.query_tools import (
    ALLOWLISTED_QUERY_TOOLS,
    QUERY_TOOL_FAMILY_MAP,
    QueryToolError,
    load_query_tool_allowlist_seed,
    run_query_tool,
    validate_query_tool_policy,
)

_EXPECTED_TOOLS = {
    "project_context",
    "source_coverage",
    "relationship_candidates",
    "accepted_relationships",
    "source_evidence_trails",
    "meeting_prep_briefs",
    "issue_history",
    "risk_digest",
    "aging_exposure",
    "review_queue_status",
    "memory_items",
    "research_packet_status",
    "evaluation_status",
}


def test_allowlist_is_the_thirteen_approved_tools() -> None:
    assert set(ALLOWLISTED_QUERY_TOOLS) == _EXPECTED_TOOLS
    assert len(ALLOWLISTED_QUERY_TOOLS) == 13


def test_family_map_covers_every_allowlisted_tool() -> None:
    assert set(QUERY_TOOL_FAMILY_MAP) == set(ALLOWLISTED_QUERY_TOOLS)


def test_seed_contract_allowlist_agree() -> None:
    seed = load_query_tool_allowlist_seed()
    contract = load_phase_08a_contract("sqlite_query_tool")
    assert set(seed["allowlisted_tools"]) == _EXPECTED_TOOLS
    assert set(contract["allowlisted_tools"]) == _EXPECTED_TOOLS


def test_policy_validates_clean() -> None:
    policy = validate_query_tool_policy()
    assert policy["valid"] is True, policy["violations"]
    assert policy["allowlisted_count"] == 13
    # Backed tools map to a registered reader family.
    assert "risk_digest" in policy["backed_tools"]
    assert "accepted_relationships" in policy["backed_tools"]


def test_contract_denies_arbitrary_and_mutation_sql() -> None:
    contract = load_phase_08a_contract("sqlite_query_tool")
    seed = load_query_tool_allowlist_seed()
    assert contract["arbitrary_sql_allowed"] is False
    assert contract["mutation_sql_allowed"] is False
    assert seed["arbitrary_sql_allowed"] is False
    assert seed["mutation_sql_allowed"] is False
    assert "no_model_generated_sql" in contract["constraints"]


@pytest.mark.parametrize(
    "bad", ["SELECT * FROM sqlite_master", "DROP TABLE query_tool_receipts", "made_up_tool"]
)
def test_non_allowlisted_tool_rejected(bad: str) -> None:
    with pytest.raises(QueryToolError):
        run_query_tool(bad, emit_receipt=False)
