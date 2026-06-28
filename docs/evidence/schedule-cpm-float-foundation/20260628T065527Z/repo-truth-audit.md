# Repo-truth audit (verified against the committed Phase 3 worktree)

## Phase 1/2/3 dependencies
- Phase 1 `schedule_cpm_graph.build_graph` → GraphBuildResult (.topological_order, fatal-diagnostic precondition via FATAL_GRAPH_DIAGNOSTICS).
- Phase 2 forward + Phase 3 backward: float reads the persisted BACKWARD run's activity rows (which already carry early+late offsets) via `get_backward_pass_run` + `list_activity_results`/`list_relationship_results`. Requires forward run (forward_pass_only) AND backward run (backward_pass_only).

## Early/late fields used (read only; application-computed)
early_start_offset_days, early_finish_offset_days, late_start_offset_days, late_finish_offset_days, duration_value, topological_index (activity rows); predecessor/successor_activity_id, relationship_type, normalized_lag_days, relationship_row_id, relationship_ref (relationship rows).

## Source float / source date fields AVOIDED (never read for logic)
imported total_float/free_float, source early_start/finish, late_start/finish, source_critical_flag, source_driving_path_flag, is_critical, derived_*_float. None are consulted; float is derived only from Phase 2/3 computed offsets.

## Total-float formula
start_based = late_start_offset_days − early_start_offset_days; finish_based = late_finish_offset_days − early_finish_offset_days. Both present & |Δ|≤1e-6 → value=start_based, basis late_start_minus_early_start, status computed. Both & differ → start_based value, status inconsistent_start_finish_float (notes record both). One present → that basis, computed. Neither → None, missing_early_late_values. Negative/fractional preserved.

## Free-float formulas (lag = normalized_lag_days)
FS: succ.ES − pred.EF − lag. SS: succ.ES − pred.ES − lag. FF: succ.EF − pred.EF − lag. SF: succ.EF − pred.ES − lag. free_float = min(candidates) only when all successor relationships supported & successor early present; else unsupported_relationship_type / missing_successor_early_values (value None). Terminal → None + not_applicable_terminal_activity. Negative preserved.

## Provenance / status values
Run: calculation_type='float', cpm_recalculation_status='forward_backward_float_only', source_run_id=backward run, total_float_computed_count, free_float_computed_count. Activity: computed_total_float(+basis/status/notes), computed_free_float(+basis/status/notes), controlling_free_float_successor_activity_id/relationship_id. Relationship: free_float_candidate(+status/notes).
