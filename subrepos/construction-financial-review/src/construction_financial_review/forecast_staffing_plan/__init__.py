"""Operator-supplied planned-staffing forecast layer for Tropical World Nursery.

Ingests the extracted staffing JSON package (``staffing_json_package_tropical_*``) as an explicit,
operator-supplied planned staffing source and turns it into a deterministic, fail-closed forecast
package. Staffing dollars are LAB-only: numeric monthly staffing forecast values map 100% to the
resolved canonical ``.LAB`` budget-code key (allocation 1.0000); the staffing schedule dates/windows
apply to the whole ``.LAB``/``.LBN``/``.MAT`` family as date-context evidence only.

Hard posture (never violated):
- CostEntries/Sage incurred cost is accounting truth; actual cost to date is the only hard floor.
- The source Excel and the extracted staffing JSON package are NEVER mutated; no accepted forecast
  package or SQLite is mutated; no live external system is called.
- Budget-code mappings are never fabricated. A cost code applies numerically only when the
  cost_code + canonical role/description family resolves to exactly ONE ``.LAB`` key AND an operator
  has accepted the mapping; otherwise it is review-only.
- The plan never silently compresses a stale accepted cost-to-complete into the plan window: the
  package emits BOTH the plan-implied monthly forecast and the current-CTC-reconciled monthly
  forecast, with the deltas and an operator-acceptance flag surfaced. Plan-driven final-cost changes
  remain advisory until an explicit operator-acceptance mechanism accepts them.
- All quantitative logic is deterministic (frozen stamp + Decimal money).
"""
