# Schedule-Integrated Forecast Package — Schema Reference

Output of `construction_financial_review.schedule_analysis.generate_schedule_integrated_forecast`.
Money is Decimal-string (2dp); float values are 8h-day schedule values; JSONL is sorted by primary
key. Generated into `schedule_integrated_forecast_package_tropical_<STAMP>/`.

## Package files

| File | Grain | Notes |
|------|-------|-------|
| `schedule_package_inventory.json` | package | schedule files, sizes, record counts, project metadata |
| `schedule_health_summary.json` | package | activity / relationship / float / cost-code-mapping health |
| `schedule_activity_inventory.jsonl` | activity | compact per-activity record |
| `schedule_relationship_inventory.jsonl` | relationship | pred/succ id, type, lag |
| `schedule_milestone_summary.jsonl` | milestone | Start/Finish Milestone activities |
| `schedule_to_budget_code_crosswalk.jsonl` | cost-code group | `mapping_status` ∈ mapped/ambiguous/manual_required/not_applicable/invalid; `mapping_method`; candidate keys; extractor candidates = supporting evidence only |
| `schedule_budget_code_rollup.jsonl` | canonical key (127) | `schedule_remaining_work_status`, `schedule_risk_level`, float/date aggregates |
| `schedule_activity_forecast_features.jsonl` | activity (1378) | full Phase-4 features incl. `is_negative_float`, `is_critical_or_longest_path` (proxy), `forecast_use` |
| `schedule_forecast_alignment_by_budget_code.jsonl` | canonical key (127) | schedule vs actual/owner/Procore; `schedule_alignment_flags`; `schedule_forecast_implication` |
| `schedule_risk_register.jsonl` | risk | schedule-derived risks with severity/materiality |
| `schedule_cashflow_timing_curve.jsonl` | key×month | duration-weighted; `allocation_confidence` capped at medium; ambiguous/unmapped → `not_allocated` |
| `schedule_mapping_review_items.jsonl` | review item | priority critical/high/medium/low |
| `forecast_recommendations_schedule_integrated.jsonl` | canonical key (127) | v2 fields preserved + `schedule_integrated_forecast_action`, `schedule_integrated_recommended_projected_cost`, `schedule_*` evidence |
| `forecast_risk_register_schedule_integrated.jsonl` | risk | v2 risks preserved (`risk_source=v2_baseline`) + schedule risks appended |
| `evidence_alignment_schedule_integrated.jsonl` | canonical key (127) | compact evidence/alignment |
| `schedule_integration_summary.json` | package | counts, action changes, blocked decreases, review counts, conclusion |
| `forecast_review_summary_schedule_integrated.md` / `executive_forecast_summary_schedule_integrated.md` | — | summaries |
| `manifest.json` / `input_inventory.json` / `validation_report.json` | — | per-file sha256, generation metadata, validation gate |
| `audit/source_files_used.json` | — | resolved input package paths |
| `audit/source_validation_snapshot.json` | — | schedule/context validation snapshot |
| `audit/schedule_health_snapshot.json` | — | copy of health summary |
| `audit/schedule_cost_code_mapping_snapshot.json` | — | crosswalk status counts |
| `audit/forecast_adjustment_trace.jsonl` | key | only rows the schedule touched |
| `audit/safety_scan_report.json` | — | sensitive-marker scan (must pass) |

## Validation checks (`validation_report.json.checks`)

`output_files_parse`, `one_recommendation_row_per_canonical_key`, `all_recommendation_keys_canonical`,
`schedule_did_not_create_numeric_increase`, `schedule_blocked_decreases_where_material`,
`cashflow_allocation_ties_to_exposure`, `no_fuzzy_mapping_method`, `mapped_budget_keys_in_canonical`,
`safety_scan_passed`. `passed` is the AND of all checks.
