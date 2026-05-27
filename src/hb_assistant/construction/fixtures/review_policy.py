"""Synthetic inventory rows for the review-policy evaluator.

Each fixture pairs an inventory-row dict (name + parent_path metadata
only) with the set of ``expected_rule_ids`` the seeded controller policy
must fire. ``clean_miss`` declares an empty set — the evaluator must
return no matches.
"""

from __future__ import annotations

from typing import Any


def _row(item_id: str, name: str, parent_path: str) -> dict[str, Any]:
    return {"item_id": item_id, "name": name, "parent_path": parent_path}


REVIEW_POLICY_FIXTURES: dict[str, dict[str, Any]] = {
    "contract_folder_hit": {
        "inventory": _row(
            "fixture-item-0101",
            "Master Agreement.pdf",
            "/Tropical/Contracts/Vendors",
        ),
        "expected_rule_ids": {"folder-contracts"},
    },
    "change_order_doc_name_hit": {
        "inventory": _row(
            "fixture-item-0102",
            "Change Order 04 - Roofing.pdf",
            "/Tropical/General",
        ),
        "expected_rule_ids": {"doc-change-order"},
    },
    "injury_term_hit": {
        "inventory": _row(
            "fixture-item-0103",
            "Worker Injury Log.pdf",
            "/Tropical/General",
        ),
        "expected_rule_ids": {"term-injury"},
    },
    "multi_rule_incident": {
        "inventory": _row(
            "fixture-item-0104",
            "Site Incident Report.pdf",
            "/Tropical/Safety/Incidents",
        ),
        "expected_rule_ids": {"folder-incidents", "term-incident"},
    },
    "low_confidence_budget": {
        "inventory": _row(
            "fixture-item-0105",
            "Budget Estimate Draft.xlsx",
            "/Tropical/General",
        ),
        "expected_rule_ids": {"term-budget-ambiguous"},
    },
    "clean_miss": {
        "inventory": _row(
            "fixture-item-0106",
            "Project Photos.zip",
            "/Tropical/General",
        ),
        "expected_rule_ids": set(),
    },
}
