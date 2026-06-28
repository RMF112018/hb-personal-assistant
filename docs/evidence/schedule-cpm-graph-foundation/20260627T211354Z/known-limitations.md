# Known limitations (by design, Phase 1)

- **CPM recalculation is NOT implemented.** This layer performs graph diagnostics only.
  Every persisted run records `cpm_recalculation_status='not_implemented'` and
  `analysis_scope='graph_diagnostics_only'`.
- **No forward/backward pass, no early/late dates, no float, no critical path, no longest
  path.** None are computed in this phase.
- **Source-export flags remain evidence only.** `source_critical_flag`,
  `source_driving_path_flag`, `source_longest_path_flag`, derived/explicit float, and
  `is_critical` are NOT read by the graph layer and are NOT relabeled as computed CPM. The
  DCMA critical-path quality metric continues to return NOT_MEASURABLE_RECALC (unchanged).
- **open_start / open_finish are graph in/out-degree diagnostics**, distinct from the DCMA
  open-ends quality metric, which is unchanged.
- **Relationship lag is carried as evidence only** (lag_value/lag_unit); it does not affect
  ordering or any computed timing.
- **No API route or frontend surface.** Service + repository + tests only.

## Next recommended phase
Phase 2: CPM forward pass (early start/finish) over the verified acyclic graph with lag
handling, writing computed values to clearly-named computed columns — never overwriting
source-export fields.
