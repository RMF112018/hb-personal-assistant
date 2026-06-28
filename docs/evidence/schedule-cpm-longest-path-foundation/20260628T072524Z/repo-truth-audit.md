# Repo-truth audit (verified against the committed Phase 4 worktree)

## Phase 1/2/3/4 dependencies
- Phase 1 build_graph → topological_order + FATAL_GRAPH_DIAGNOSTICS precondition.
- Reads the persisted Phase 4 FLOAT run: list_activity_results (early/late offsets, total/free float, duration, topo index, ISO dates) + list_relationship_results (predecessor/successor, relationship_type, normalized_lag_days, candidate_successor_early_start_offset, relationship_ref/row_id). Requires forward run (forward_pass_only) AND float run (forward_backward_float_only); the float run transitively required backward.

## Result fields used (read only; application-computed)
early_start/finish_offset_days, late_start/finish_offset_days, computed_total_float, computed_free_float, duration_value, topological_index, computed_early/late_* (ISO), activity_name (activity rows); predecessor/successor_activity_id, relationship_type, normalized_lag_days, candidate_successor_early_start_offset, relationship_ref, relationship_row_id (relationship rows).

## Source fields AVOIDED (never read for logic)
imported/source early/late dates, total/free/derived float, source_critical_flag, source_driving_path_flag, is_critical, longest/critical path source flags. None consulted.

## Endpoint selection
max early_finish_offset_days → tie: larger early_start_offset_days → tie: lower topological_index → tie: lexicographically smallest activity_id. Tie note recorded when ≥2 share the max early finish.

## Backtrace formulas (forward candidate basis; lag = normalized_lag_days)
Prefer persisted candidate_successor_early_start_offset. Reconstruct when absent: FS pred.EF+lag; SS pred.ES+lag; FF pred.EF+lag−succ_dur; SF pred.ES+lag−succ_dur. Controlling predecessor = candidate == successor.early_start_offset_days within 1e-6.

## Tie-break (controlling predecessor)
larger pred early_finish → larger pred early_start → lower pred topological_index → smallest pred activity_id → smallest relationship_ref.

## Provenance / status values
Run: calculation_type='longest_path', cpm_recalculation_status='longest_path_only', source_run_id=float run, path_count, longest_path_activity_count/relationship_count/duration/end_activity_id. Path: path_type, path_rank, start/end activity, counts, span offsets, path_duration, path_total_float (nullable, NOT criticality), path_basis='max_forward_early_finish_backtrace', path_status (computed|degraded_partial_backtrace|unsupported_relationship_type|...). Path activity: path_sequence, relationship_from_previous, computed early/late offsets, total/free float, duration, selection_basis.
