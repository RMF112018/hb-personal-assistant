# Repo-truth audit (verified against the committed Phase 2 worktree)

## Phase 1 dependency
`schedule_cpm_graph.build_graph` → `GraphBuildResult` (.topological_order, .is_acyclic, .diagnostics). Reverse topo = `reversed(topological_order)`. FATAL_GRAPH_DIAGNOSTICS reused.

## Phase 2 dependency
`schedule_cpm_forward_pass` constants (SUPPORTED_RELATIONSHIP_TYPES, RUN_BLOCKED, _OFFSET_DECIMALS). Forward results read from the persisted forward run via `get_forward_pass_run` + `list_activity_results`/`list_relationship_results`. Start anchor parsed from the forward run's `schedule_start_anchor`.

## Activity result fields used (read)
activity_id, duration_value, early_start_offset_days, early_finish_offset_days (+ pass-through: activity_name, topological_index, computed_early_*, duration_unit/source, predecessor/successor_count, forward_pass_status copied into the backward run rows).

## Relationship result fields used (read)
predecessor_activity_id, successor_activity_id, relationship_type, normalized_lag_days, relationship_row_id, relationship_ref (+ early fields copied: lag_value/unit, predecessor_early_*_offset, candidate_successor_early_start_offset, relationship_calc_status).

## Finish-anchor precedence (implemented)
1. Imported scheduled finish = max parseable activity `finish_date` → offset = calendar-day delta from start anchor (source `source_scheduled_finish`).
2. Imported planned finish = max parseable `planned_finish` (source `source_planned_finish`).
3. max forward early-finish offset (source `max_forward_early_finish`).
4. else block `missing_finish_anchor`.
Uses imported finish dates only — never source `early_finish`/`late_finish`/float/critical flags, never for logic. Earlier-than-forward → caveat, not failure.

## Duration handling
Reuses the forward run's persisted `duration_value` (already normalized to working-day-equivalent days in Phase 2). No re-normalization; backward never re-reads raw source durations.

## Lag handling
Reuses the forward run's persisted `normalized_lag_days` per relationship. No re-normalization.

## Relationship formulas (implemented; lag = normalized_lag_days)
- FS: cand_pred_LF = succ.LS − lag; cand_pred_LS = cand_LF − dur(pred).
- SS: cand_pred_LS = succ.LS − lag; cand_pred_LF = cand_LS + dur(pred).
- FF: cand_pred_LF = succ.LF − lag; cand_pred_LS = cand_LF − dur(pred).
- SF: cand_pred_LS = succ.LF − lag; cand_pred_LF = cand_LS + dur(pred).
Predecessor LF = min controlling candidate over successors (tie-break sorted succ id then ref); LS = LF − duration. Terminal (out-degree 0) LF = finish anchor.
