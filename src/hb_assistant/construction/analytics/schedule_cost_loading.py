"""Deterministic cost-loaded schedule detection."""

from __future__ import annotations

from typing import Any

MIN_COVERAGE_RATIO = 0.05
MIN_ACTIVITY_COUNT = 3


def assess_cost_loaded_status(
    activities: list[dict[str, Any]],
    hints: list[dict[str, Any]],
) -> str:
    """Return not_cost_loaded | possible | verified | unreconciled.

    Conservative: never returns verified without strong multi-activity evidence.
    """
    if not activities:
        return "not_cost_loaded"

    with_cost = 0
    for act in activities:
        if any(
            act.get(k)
            for k in (
                "cost_loaded_amount",
                "cost_loaded_quantity",
                "cost_code",
                "cost_account_id",
            )
        ):
            with_cost += 1

    hint_count = len(hints)
    total = len(activities)
    ratio = with_cost / total if total else 0.0

    if with_cost < MIN_ACTIVITY_COUNT and hint_count < MIN_ACTIVITY_COUNT:
        return "not_cost_loaded"

    if ratio >= MIN_COVERAGE_RATIO or hint_count >= MIN_ACTIVITY_COUNT:
        # Possible only — operator review required before verified.
        return "possible"

    if with_cost == 1 and hint_count <= 1:
        return "not_cost_loaded"

    return "possible"