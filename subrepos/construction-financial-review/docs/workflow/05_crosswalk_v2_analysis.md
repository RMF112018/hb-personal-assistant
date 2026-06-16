# Stage 5 — Crosswalk-aware forecast analysis v2

**Generator:** `src/construction_financial_review/analysis/generate_forecast_analysis_crosswalk_v2.py`.

Re-runs the forecast analysis using the **authoritative crosswalk** so owner pay-app, Procore
subcontractor, BudgetDetails, and CostEntries evidence is compared at the correct **owner-scope
rollup** level instead of inferred child-level matching.

- One-to-many owner SOV scopes are compared only at `owner_scope_rollup`; owner summary dollars are
  **not allocated** to child budget codes (no allocation schedule). Children inherit rollup context only.
- The prior 32 critical `owner_procore_mismatch` flags are reclassified as structural
  (`crosswalk_applied_structural_mismatch_resolved`, informational) with full old→new traceability.
- Floor-to-actuals increases remain mandatory; actuals-only holds are `medium` unless no-exposure proven.
- Hard crosswalk gate: fails the package unless 127/127, 42/42, 0 unresolved, 0 duplicate, and the
  named facts all hold.

Output: `forecast_analysis_package_tropical_crosswalk_v2_<stamp>/`. Conclusion:
`forecast_analysis_crosswalk_v2_ready_with_review_items`.
