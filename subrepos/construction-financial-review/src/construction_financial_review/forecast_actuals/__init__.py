"""Shared month-by-month actual-cost export contract for the forecast packages.

Every forecast package emits byte-identical actual-incurred-cost-by-month exports for each canonical
budget code, sourced ONLY from CostEntries/Sage (the context package's
``canonical/monthly_actuals_by_budget_code.jsonl``, which carries ``source: "CostEntries"``). Reading
only that file structurally guarantees no owner/subcontractor pay-application, prior-forecast, staffing-
plan, schedule, or operator-control value is ever treated as an actual. This is an additive evidence/
export contract — it never changes any forecast recommendation value, never mutates an actual, and is
deterministic (Decimal-string money, stable ordering).
"""
