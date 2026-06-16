# Stage 6 — Schedule-Integrated Forecast

Layers the P6/XER-derived **schedule package** onto the crosswalk-v2 forecast recommendations.
Schedule data is treated strictly as **timing / remaining-work / sequencing / risk** evidence.

## Inputs

- **Schedule package** `project_schedule_json_package/` — `schedule_project_manifest.json`,
  `schedule_activities.jsonl`, `schedule_relationships.jsonl`, `schedule_validation_report.json`.
- **Forecast context package** (latest `forecast_context_package_tropical_*`) — canonical 127
  BudgetDetails keys + per-budget-code actuals/owner/Procore context.
- **Crosswalk-v2 analysis package** (latest `forecast_analysis_package_tropical_crosswalk_v2_*`) —
  baseline `forecast_recommendations_by_budget_code.jsonl` and `forecast_risk_register.jsonl`.
- **Mapping-discrepancy workpaper** (optional, latest) — consumed read-only to avoid
  over-interpreting owner-vs-Procore mismatches.

Packages are discovered from `config/projects/tropical.json` (config-named first, else latest match).

## What schedule evidence MAY do

- Strengthen `review_required`, add remaining-exposure / forecast-exhaustion flags.
- **Block** an automatic `decrease_forecast` (downgrade to `review_required`, clear the number).
- Support a cash-flow timing curve over remaining exposure (timing only).
- Lower confidence where open work coincides with forecast exhaustion.

## What schedule evidence MUST NOT do

- Set `recommended_projected_cost`, create a numeric increase, or create a new decrease.
- Override accounting actuals or owner/Procore evidence.
- Force a budget-code mapping, use fuzzy matching, or treat duration %-complete as cost %-complete.
- Treat negative float alone as a cost overrun.

## Deterministic rules (approved)

| Rule | Value |
|------|-------|
| Forecast exhaustion (`actuals_near_projected`) | `actual_cost_all_source_to_date >= 0.90 * current_projected_cost` |
| Material remaining work | `>= 3` open activities **OR** `>= 14` remaining 8h-days |
| Critical / longest-path | `total_float <= 0` **proxy only** (no explicit longest-path flag in source) |
| Risk **escalation** | uses **negative** float (`< 0`) on **open** work — never zero float alone |
| Cash-flow allocation | duration-weighted across months; confidence **capped at medium** |
| Ambiguous / unmapped exposure | stays `not_allocated` |

## Mapping authority

The canonical BudgetDetails universe is the **sole** mapping authority. A schedule cost code that
resolves to exactly one canonical key is `mapped` (high). A cost code spanning multiple categories
(e.g. `15-16-110` → `.MAT` and `.SUB`) is `ambiguous` — no single key is assigned. The schedule
extractor's `candidate_budget_code_keys` are recorded as **supporting evidence only** and can never
create a `mapped` key.

## Output

One new timestamped package
`schedule_integrated_forecast_package_tropical_YYYYMMDD_HHMMSS/` under the data root, with the
schedule inventories, crosswalk, rollup, alignment, risk register, cash-flow curve, the
schedule-integrated recommendations (one row per canonical 127), summaries, and an `audit/` folder
(source files, validation snapshots, adjustment trace, safety scan). See
`src/construction_financial_review/schemas/schedule_integrated_forecast_schema.md`.

## Run

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli schedule-integrate-forecast --project tropical
```

Conclusion is one of `schedule_integrated_forecast_ready`,
`schedule_integrated_forecast_ready_with_review_items`, or `schedule_integrated_forecast_not_ready`.
