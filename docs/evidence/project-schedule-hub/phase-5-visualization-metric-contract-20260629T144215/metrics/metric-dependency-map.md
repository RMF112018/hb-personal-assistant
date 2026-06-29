# Metric Dependency Map

## `monthly_activity_start_finish_distribution`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `project_schedule_baseline_selections`, `schedule_cpm_activity_results`, `schedule_file_imports`
- Basis labels: source_export, baseline, selected_baseline, computed_cpm, current_update

## `planned_vs_actual_percent_complete`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_file_imports`
- Basis labels: source_export, prior_update, current_update

## `schedule_performance_ratio`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_file_imports`
- Basis labels: source_export, prior_update, current_update

## `schedule_delay_over_time`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_version_diffs`, `project_schedule_baseline_selections`, `schedule_baseline_projects`
- Basis labels: source_export, prior_update, selected_baseline, baseline, diff_derived

## `schedule_changes_over_time`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `schedule_version_diffs`, `schedule_version_diff_detail_facts`, `schedule_version_diff_impact_rollups`, `schedule_cpm_activity_results`
- Basis labels: diff_derived, computed_cpm, prior_update

## `delay_analysis`
- Readiness: `ready_after_udf_normalization`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_version_diff_detail_facts`, `schedule_version_diff_impact_rollups`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, diff_derived, prior_update, udf_derived

## `window_start_accuracy`
- Readiness: `ready_after_udf_normalization`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `project_schedule_baseline_selections`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, selected_baseline, baseline, prior_update, current_update, udf_derived

## `window_finish_accuracy`
- Readiness: `ready_after_udf_normalization`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `project_schedule_baseline_selections`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, selected_baseline, baseline, prior_update, current_update, udf_derived

## `should_have_finished_status`
- Readiness: `ready_after_udf_normalization`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_cpm_activity_results`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, computed_cpm, current_update, udf_derived

## `schedule_compression_ratio`
- Readiness: `ready_after_baseline_selection`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `schedule_baseline_activity_crosswalk`, `project_schedule_baseline_selections`
- Basis labels: source_export, baseline, selected_baseline, prior_update

## `project_schedule_health_index`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `schedule_quality_evaluation_runs`, `schedule_quality_metric_results`, `schedule_quality_scorecards`, `schedule_quality_findings`, `procore_ep_schedule_activities`, `schedule_cpm_activity_results`
- Basis labels: quality_derived, source_export, computed_cpm, selected_baseline, current_update

## `schedule_feasibility_score`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: `schedule_performance_ratio`, `schedule_compression_ratio`, `project_schedule_health_index`
- Table dependencies: `procore_ep_schedule_activities`, `schedule_quality_scorecards`, `schedule_cpm_activity_results`, `project_schedule_baseline_selections`
- Basis labels: source_export, computed_cpm, quality_derived, selected_baseline, prior_update, current_update

## `required_recovery_days`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `schedule_cpm_paths`, `schedule_cpm_path_activities`, `schedule_cpm_activity_results`, `procore_ep_schedule_activities`
- Basis labels: computed_cpm, prior_update, source_export

## `critical_path_length_index`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `schedule_cpm_paths`, `schedule_cpm_path_activities`, `schedule_cpm_activity_results`, `procore_ep_schedule_activities`
- Basis labels: computed_cpm, source_export, prior_update, current_update

## `total_float_consumption_index`
- Readiness: `ready_after_trend_aggregation`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_cpm_activity_results`
- Basis labels: source_export, computed_cpm, prior_update, current_update

## `critical_issues_category_model`
- Readiness: `ready_after_udf_normalization`
- Metric dependencies: none
- Table dependencies: `procore_ep_schedule_activities`, `schedule_cpm_activity_results`, `schedule_quality_findings`, `schedule_quality_metric_results`, `project_schedule_review_items`, `project_schedule_review_item_events`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, computed_cpm, quality_derived, prior_update, current_update, udf_derived
