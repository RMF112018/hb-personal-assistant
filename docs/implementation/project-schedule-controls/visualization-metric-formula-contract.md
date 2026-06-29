# Project Schedule Controls Phase 5 Visualization Metric Formula Contract

Date: 2026-06-29

## Executive Summary

Phase 5 defines a contract-only formula registry for future Project Schedule Hub visualizations. The implementation is backend-only and declarative: it defines metric names, formulas, DB mappings, basis labels, readiness, thresholds, caveats, and future payload recommendations. It does not implement chart aggregation services, trend API routes, frontend charts, baseline override, recurring reports, or import pipeline changes.

The contract is exposed by `ProjectScheduleVisualizationMetricContractService` and the module-level helpers `get_visualization_metric_contracts()` and `get_visualization_metric_readiness_matrix()`.

## Scope And Non-Scope

In scope:

- Sixteen neutral internal metric contracts.
- SQLite/schema-backed source table and column mapping.
- UDF dependency mapping and readiness caveats.
- Configurable threshold and weighting declarations.
- Future API payload recommendations.
- Evidence package generation.

Out of scope:

- Dashboard charts and frontend UI.
- Heavy metric aggregation or trend APIs.
- Baseline override workflow.
- Import pipeline changes.
- Cost-weighted primary progress/SPI until cost/resource loading is validated.
- Causation, entitlement, responsibility, or compensability findings.

## Formula Registry

Required internal metric keys:

- `monthly_activity_start_finish_distribution`
- `planned_vs_actual_percent_complete`
- `schedule_performance_ratio`
- `schedule_delay_over_time`
- `schedule_changes_over_time`
- `delay_analysis`
- `window_start_accuracy`
- `window_finish_accuracy`
- `should_have_finished_status`
- `schedule_compression_ratio`
- `project_schedule_health_index`
- `schedule_feasibility_score`
- `required_recovery_days`
- `critical_path_length_index`
- `total_float_consumption_index`
- `critical_issues_category_model`

Internal keys are neutral and do not use proprietary-style product names. Display aliases may use common industry terms such as SPI only when the basis is explicit.

## Metric Contracts

The source of truth is the registry in `project_schedule_visualization_metric_contract.py`. Each metric includes:

- PM-facing purpose.
- Formula summary and formula detail.
- Source tables and columns.
- UDF dependencies.
- Comparison basis and weighting basis.
- Default weighting basis.
- Configurable thresholds and weights.
- Readiness status and blockers.
- Caveats and notes.
- Future API payload shape.
- Required tests.
- Basis labels.

## DB Table And Column Mapping

Primary table families mapped by the registry:

- Current schedule facts: `procore_ep_schedule_activities`, `procore_ep_schedule_relationships`, `procore_ep_schedule_wbs_nodes`, `procore_ep_schedule_calendars`, `schedule_file_imports`.
- Generic UDF storage: `procore_ep_schedule_udf_values`.
- Baseline facts: `schedule_baseline_projects`, `schedule_baseline_activities`, `schedule_baseline_relationships`, `schedule_baseline_activity_crosswalk`, `project_schedule_baseline_selections`.
- CPM facts: `schedule_cpm_runs`, `schedule_cpm_activity_results`, `schedule_cpm_relationship_results`, `schedule_cpm_diagnostics`, `schedule_cpm_paths`, `schedule_cpm_path_activities`.
- Diff facts: `schedule_version_diffs`, `schedule_version_diff_detail_facts`, `schedule_version_diff_impact_rollups`, `schedule_version_diff_facts`.
- Quality facts: `schedule_quality_evaluation_runs`, `schedule_quality_metric_results`, `schedule_quality_scorecards`, `schedule_quality_findings`.
- Review workflow facts: `project_schedule_review_items`, `project_schedule_review_item_events`.

The Phase 5 tests validate the registry's mapped columns against a migrated SQLite schema. Missing mapped columns fail the contract tests.

## UDF Dependency Mapping

Generic UDF storage exists in `procore_ep_schedule_udf_values` with `udf_type_name`, `udf_data_type`, and `udf_value`. That proves generic queryability, not stable named UDF normalization.

Named UDF-dependent metrics are therefore not `ready_now`. Dependencies include:

- `OLD ID`
- `PHASE`
- `FLOOR`
- `SECTOR / AREA`
- `SUBCONTRACTOR`
- `Cost Code`
- `Filter Out`
- `Start Previous Status`
- `Finish Previous Status`
- `Update Notes`
- `Schedule Review Comments`

## Readiness Matrix

Approved readiness statuses:

- `ready_now`
- `ready_after_api_contract`
- `ready_after_cpm_reconciliation`
- `ready_after_udf_normalization`
- `ready_after_baseline_selection`
- `ready_after_trend_aggregation`
- `ready_after_cost_loading_validation`
- `deferred`

Phase 5 intentionally classifies most visualization metrics as not ready for chart implementation because trend aggregation, selected-baseline workflows, named UDF normalization, or cost-loading validation are still required for production metric computation.

## Configurable Thresholds And Weights

Required configurable values include:

- Critical threshold default: `critical_float_threshold_days = 1`.
- Near-critical threshold default: `near_critical_float_threshold_days = 10`.
- Schedule compression thresholds: green `0-14%`, yellow `15-25%`, red `>25%`.
- Window accuracy lookback/lookahead days.
- Health Index component weights for logic density, float, critical duration, constraints, update quality, and compression.
- Feasibility Score component weights for compression, negative float, health index, performance ratio, and forecast variance.

## Basis Labels

Every metric declares basis labels from this fixed set:

- `source_export`
- `computed_cpm`
- `baseline`
- `selected_baseline`
- `prior_update`
- `current_update`
- `udf_derived`
- `quality_derived`
- `diff_derived`

These labels prevent mixing source/export float with computed CPM float, baseline variance with prior-update movement, and generic UDF storage with stable named UDF normalization.

## Future API Payload Recommendations

Future APIs should use the registry's `future_api_payload_shape` values as the starting contract. Phase 6 trend aggregation should consume the registry rather than creating new formula definitions in route code.

Future payloads should always include:

- Metric key.
- Data date or period.
- Comparison basis.
- Weighting basis.
- Basis labels.
- Readiness/provenance where source quality affects interpretation.
- Drilldown link only after a route contract exists.

## Testing Requirements

Phase 5 tests prove:

- All 16 metric keys are present and neutral.
- Required contract fields are populated.
- Readiness statuses and basis labels are approved values.
- Mapped columns exist in a migrated SQLite schema.
- Duration-weighted progress/SPI defaults are declared.
- Cost-weighted variants remain blocked.
- Critical threshold and Health Index weights are configurable.
- UDF-dependent metrics are not `ready_now`.
- Non-causation caveats are present.
- The module is contract-only and does not add routes, chart code, mutating SQL, baseline override, or import pipeline behavior.

The validation bundle also reruns Project Schedule Hub canonical regression tests to preserve Phase 1 behavior.

## Deferred Items

- Trend aggregation APIs and chart-ready datasets.
- Baseline override workflow.
- Named UDF normalization.
- Cost/resource loading validation for cost-weighted progress/SPI.
- Critical issue panel aggregation and review item generation.
- Recurring reports, automation, and PDF export.

## Caveats And Guardrails

- Delay, driver, required recovery, and critical issue metrics are PM review cues only. They are not causation, entitlement, responsibility, or compensability findings.
- TWNU07 may be used as a Tropical fixture baseline only. It is not a product-wide default.
- Source/export float and computed CPM float must remain separate unless the payload explicitly labels both.
- Prior-update movement and baseline variance must remain separately labeled.
