# Repo-truth audit (verified against the committed Phase 5 worktree)

## Phase 1/2/3/4/5 dependencies
- Phase 1 build_graph → topological_order + FATAL_GRAPH_DIAGNOSTICS precondition.
- Phase 4 FLOAT run: list_activity_results → computed_total_float, computed_free_float, early/late offsets+ISO, duration, topo index, activity_name. Required (forward_backward_float_only).
- Phase 5 LONGEST-PATH run: list_paths → list_path_activities → activity_id, path_sequence (membership). Required (longest_path_only).

## Result fields used (read only; application-computed)
computed_total_float (classification input); computed_free_float, early/late offsets+ISO, duration, topo index, activity_name, pred/succ counts (whitelist-copied context); path_sequence (membership).

## Source fields AVOIDED (never read for logic, never whitelisted)
source/imported total_float/free_float, derived float, source_critical_flag, explicit/source critical, source_driving_path_flag, imported early/late dates, is_critical. The FLOAT_ROW_WHITELIST excludes all of these (asserted by test).

## Thresholds
critical_float_threshold_days=0.0, near_critical_float_threshold_days=10.0, float_tolerance_days=1e-6 (all configurable). Validated before classification (critical≤near, tolerance≥0, finite) else block invalid_criticality_thresholds.

## Classification rules
tf None→unclassified/missing_computed_total_float. tf≤crit+tol→computed_critical (flag). crit<tf≤near+tol→computed_near_critical (flag). tf>near+tol→computed_noncritical. Negative tf→computed_critical (never clamped).

## Longest-path membership treatment
Context only (longest_path_member_flag/sequence/basis). NEVER overrides class. Caveats recorded but do not change class.

## Caveat rules
negative_total_float (tf<0); threshold_boundary_value (|tf−threshold|≤tol); zero_float_not_on_longest_path (critical but not member); longest_path_member_not_zero_float (member but not critical).

## Provenance / status values
Run: calculation_type='criticality', cpm_recalculation_status='criticality_classification_only', source_run_id=longest-path run, thresholds + 5 class counts + longest_path_member_count. Activity: computed_total/free_float, computed_critical/near_critical_flag, computed_criticality_class/status/basis/notes, thresholds, longest_path_member_flag/sequence/basis.
