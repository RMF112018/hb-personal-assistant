# Repo-truth audit (verified against the committed Phase 6 worktree)

## Quality engine
- `schedule_quality_engine.py::_metric_critical_path_test` (line ~1426) returns METRIC_STATUS_NOT_MEASURABLE_RECALC for primavera_xer/ms_project_xml before any other logic; `_base_metric` builds metric dicts (metric_family default 'dcma'); source-export (`_evaluate_source_export_metrics`) + supplemental proxy are SEPARATE lists; scorecard filters metric_family=='dcma'. MEASURED_STATUSES gates scorecard "measured" inclusion.
- EvaluationContext had no db_path; ScheduleQualityDataLoader (has db_path) + run_evaluation_for_run build the context. classify_critical_path_readiness (schedule_quality_posture.py) hardcoded available_cpm_recalculated=False.

## Status CHECK constraint (why a migration was required)
schedule_quality_metric_results.status is CHECK-constrained to METRIC_STATUS_CHECK_VALUES (store/schedule_float_tables.py), rebuilt by table-recreate reconciles (V65/V67/V70/V71). A new measurable status therefore requires a migration (V89) — mirrored the V71 rename→CREATE(new CHECK)→copy→drop→reindex pattern, guarded by a DDL substring check.

## Phase 1–6 CPM dependencies + statuses used
forward 'forward_pass_only', backward 'backward_pass_only', float 'forward_backward_float_only', longest_path 'longest_path_only', criticality 'criticality_classification_only'. Read via repo get_*_run + list_activity_results/list_paths/list_path_activities. The criticality run's activity_results carry computed_total_float + computed_criticality_class (the classification used).

## Path-integrity checks
exactly one path_rank=1 'longest_path' row with path_status=='computed'; ordered path-activity rows; path_sequence contiguous from 1; each activity after the first has relationship_from_previous_ref; path_finish_offset == end activity early_finish within 1e-6; path_duration == finish−start within 1e-6.

## Criticality-consistency checks
each longest-path activity has a criticality row with computed_total_float present and a class set; ALL longest-path activities must be computed_critical for measurable; any unclassified/missing/near-critical/noncritical → not measurable (specific reason). computed_critical outside the longest path → caveat, not failure.

## Source fields AVOIDED
source total/derived float, source_critical_flag, source_driving_path_flag, imported early/late, is_critical — none read as computation inputs; source-export evidence preserved as separate metrics.

## Status values
new: available_app_cpm_recalculated (measured). reused: not_measurable_requires_recalculation (attempted-incomplete / source-only). basis label: application_computed_cpm.
