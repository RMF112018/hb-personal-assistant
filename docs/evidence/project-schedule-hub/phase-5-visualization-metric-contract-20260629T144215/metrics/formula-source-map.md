# Formula Source Map

## `monthly_activity_start_finish_distribution`
- Formula: Bucket activity start and finish dates by month for each selected date family.
- Tables: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `project_schedule_baseline_selections`, `schedule_cpm_activity_results`, `schedule_file_imports`
- Basis labels: source_export, baseline, selected_baseline, computed_cpm, current_update

## `planned_vs_actual_percent_complete`
- Formula: Default actual progress is duration weighted: sum(percent_complete * original_duration) / sum(original_duration).
- Tables: `procore_ep_schedule_activities`, `schedule_file_imports`
- Basis labels: source_export, prior_update, current_update

## `schedule_performance_ratio`
- Formula: Default ratio is duration-weighted EV-like progress divided by duration-weighted PV-like planned progress.
- Tables: `procore_ep_schedule_activities`, `schedule_file_imports`
- Basis labels: source_export, prior_update, current_update

## `schedule_delay_over_time`
- Formula: For each period, compare current forecast finish to prior forecast finish and selected baseline finish separately.
- Tables: `procore_ep_schedule_activities`, `schedule_version_diffs`, `project_schedule_baseline_selections`, `schedule_baseline_projects`
- Basis labels: source_export, prior_update, selected_baseline, baseline, diff_derived

## `schedule_changes_over_time`
- Formula: Aggregate persisted diff facts by update period and change category.
- Tables: `schedule_version_diffs`, `schedule_version_diff_detail_facts`, `schedule_version_diff_impact_rollups`, `schedule_cpm_activity_results`
- Basis labels: diff_derived, computed_cpm, prior_update

## `delay_analysis`
- Formula: Combine prior-update movement, diff impact rollups, and candidate driver facts for PM review.
- Tables: `procore_ep_schedule_activities`, `schedule_version_diff_detail_facts`, `schedule_version_diff_impact_rollups`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, diff_derived, prior_update, udf_derived

## `window_start_accuracy`
- Formula: On-time starts divided by total planned starts in the configured window.
- Tables: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `project_schedule_baseline_selections`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, selected_baseline, baseline, prior_update, current_update, udf_derived

## `window_finish_accuracy`
- Formula: Finished-on-time count divided by total planned finishes in the configured window.
- Tables: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `project_schedule_baseline_selections`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, selected_baseline, baseline, prior_update, current_update, udf_derived

## `should_have_finished_status`
- Formula: Activities due by data date are classified as on track, at risk, or delayed using finish, progress, status, float, and criticality facts.
- Tables: `procore_ep_schedule_activities`, `schedule_cpm_activity_results`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, computed_cpm, current_update, udf_derived

## `schedule_compression_ratio`
- Formula: Compression percentage = ((baseline/comparison remaining duration / current remaining duration) - 1) * 100.
- Tables: `procore_ep_schedule_activities`, `schedule_baseline_activities`, `schedule_baseline_activity_crosswalk`, `project_schedule_baseline_selections`
- Basis labels: source_export, baseline, selected_baseline, prior_update

## `project_schedule_health_index`
- Formula: Weighted penalty model on a 0-100 scale using schedule quality, float, critical duration, constraints, update quality, and compression inputs.
- Tables: `schedule_quality_evaluation_runs`, `schedule_quality_metric_results`, `schedule_quality_scorecards`, `schedule_quality_findings`, `procore_ep_schedule_activities`, `schedule_cpm_activity_results`
- Basis labels: quality_derived, source_export, computed_cpm, selected_baseline, current_update

## `schedule_feasibility_score`
- Formula: Composite score from compression, negative float, health index, schedule performance ratio, and forecast completion variance.
- Tables: `procore_ep_schedule_activities`, `schedule_quality_scorecards`, `schedule_cpm_activity_results`, `project_schedule_baseline_selections`
- Basis labels: source_export, computed_cpm, quality_derived, selected_baseline, prior_update, current_update

## `required_recovery_days`
- Formula: Required recovery days = critical path delay minus forecast finish movement.
- Tables: `schedule_cpm_paths`, `schedule_cpm_path_activities`, `schedule_cpm_activity_results`, `procore_ep_schedule_activities`
- Basis labels: computed_cpm, prior_update, source_export

## `critical_path_length_index`
- Formula: Compare critical/near-critical progress against planned progress using duration-weighted path or subset durations.
- Tables: `schedule_cpm_paths`, `schedule_cpm_path_activities`, `schedule_cpm_activity_results`, `procore_ep_schedule_activities`
- Basis labels: computed_cpm, source_export, prior_update, current_update

## `total_float_consumption_index`
- Formula: Float consumed between updates divided by elapsed time or planned float allowance for the selected critical/near-critical subset.
- Tables: `procore_ep_schedule_activities`, `schedule_cpm_activity_results`
- Basis labels: source_export, computed_cpm, prior_update, current_update

## `critical_issues_category_model`
- Formula: Classify issue candidates into five PM-facing categories with severity, drilldown basis, review eligibility, and caveats.
- Tables: `procore_ep_schedule_activities`, `schedule_cpm_activity_results`, `schedule_quality_findings`, `schedule_quality_metric_results`, `project_schedule_review_items`, `project_schedule_review_item_events`, `procore_ep_schedule_udf_values`
- Basis labels: source_export, computed_cpm, quality_derived, prior_update, current_update, udf_derived
