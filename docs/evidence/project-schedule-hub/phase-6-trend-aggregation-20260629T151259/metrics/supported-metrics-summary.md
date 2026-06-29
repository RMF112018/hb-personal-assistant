# Supported Phase 6 Trend Metrics

- `monthly_activity_start_finish_distribution`: Monthly Activity Start/Finish Distribution; default weighting `activity_count`; basis source_export, baseline, selected_baseline, computed_cpm, current_update
- `planned_vs_actual_percent_complete`: Planned vs Actual Percent Complete; default weighting `duration_weighted`; basis source_export, prior_update, current_update
- `schedule_performance_ratio`: Schedule Performance Ratio; default weighting `duration_weighted`; basis source_export, prior_update, current_update
- `schedule_delay_over_time`: Schedule Delay Over Time; default weighting `calendar_days`; basis source_export, prior_update, selected_baseline, baseline, diff_derived
- `schedule_changes_over_time`: Schedule Changes Over Time; default weighting `change_count`; basis diff_derived, computed_cpm, prior_update
- `project_schedule_health_index`: Project Schedule Health Index; default weighting `weighted_penalty_model`; basis quality_derived, source_export, computed_cpm, selected_baseline, current_update
- `schedule_feasibility_score`: Schedule Feasibility Score; default weighting `weighted_composite`; basis source_export, computed_cpm, quality_derived, selected_baseline, prior_update, current_update
- `required_recovery_days`: Required Recovery Days; default weighting `calendar_days`; basis computed_cpm, prior_update, source_export
- `critical_path_length_index`: Critical Path Length Index; default weighting `duration_weighted`; basis computed_cpm, source_export, prior_update, current_update
- `total_float_consumption_index`: Total Float Consumption Index; default weighting `float_days`; basis source_export, computed_cpm, prior_update, current_update
