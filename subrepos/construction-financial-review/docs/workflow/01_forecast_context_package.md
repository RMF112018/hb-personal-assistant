# Stage 1 — Forecast context package

**Generator:** `src/construction_financial_review/context/generate_forecast_context_package.py`
(verbatim, validated copy from the 2026-June Tropical run).

Combines, maps, reconciles, and structures the workbook budget/cost actuals, owner pay-app, and
Procore subcontractor pay-app source packages into one consolidated, agent-ingestible context package.

- BudgetDetails is the master 127-key budget-code universe.
- CostEntries are accounting actual-cost truth (June 2026 actuals bucketed separately).
- Deterministic mapping only (exact + parsed + owner family); no fuzzy matching.
- Procore subcontractor data is through May 2026 (cutoff enforced; 0 records ≥ 2026-06-01).
- Safety scan + reconciliation + row-count validation; deterministic sorted output.

Output: `forecast_context_package_tropical_<stamp>/`. Conclusion:
`forecast_context_ready_with_mapping_gaps`. See `schemas/forecast_context_schema.md`.
