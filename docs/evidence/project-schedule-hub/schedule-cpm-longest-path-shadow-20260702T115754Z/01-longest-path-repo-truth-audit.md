# Longest-path repo-truth audit

Phase A audit for CPM longest-path shadow replay (formula trace v2).

## Algorithm source

Production: `src/hb_assistant/construction/analytics/schedule_cpm_longest_path.py`

- Basis: `max_forward_early_finish_backtrace` (`PATH_BASIS`)
- End activity: max `early_finish_offset_days`; ties → larger ES → lower topo index → smallest `activity_id`
- Backtrace: controlling predecessor per activity via `_candidate()` + `_tie_break()`
- Persisted: `schedule_cpm_paths` + `schedule_cpm_path_activities` (`path_rank = 1` primary path)

## Pinned definition: `path_duration`

From `_build_summary()`:

| Field | Definition |
|-------|------------|
| `path_start_offset_days` | `early_start_offset_days` of first activity on path (start → end order) |
| `path_finish_offset_days` | `early_finish_offset_days` of last activity on path |
| `path_duration` | `path_finish_offset_days - path_start_offset_days` (rounded to 6 decimals) |

**Not** the sum of activity `duration_value` on the path. Lag and SS/FF/SF semantics affect controlling-predecessor selection; elapsed span can differ from summed durations.

Shadow output, persisted comparison, audit report, and JSONL trace use this same basis.

## Relationship semantics (`_candidate`)

1. Unsupported `relationship_type` → excluded from controlling match.
2. If `candidate_successor_early_start_offset` is persisted on the float relationship row → use persisted value (Phase 2 forward candidate).
3. Else reconstruct:
   - FS: `pred_EF + lag`
   - SS: `pred_ES + lag`
   - FF: `pred_EF + lag - succ_duration`
   - SF: `pred_ES + lag - succ_duration`
4. Controlling predecessor: candidate within `_TOL` (1e-6) of successor `early_start_offset_days`.
5. Tie-break on matches: larger pred EF → larger pred ES → lower pred topo → smallest pred id → smallest `relationship_ref`.

Shadow must mirror these semantics exactly.

## Persisted path identity mapping

`schedule_cpm_path_activities` stores:

- `relationship_from_previous_id` — maps to `relationship_row_id` in float/forward relationship rows when present
- `relationship_from_previous_ref` — human/canonical ref string

First path activity has both null (`selection_basis: path_start`).

**Comparison rule:** use normalized identity block with ref + id + pred + succ + type + lag. When id is absent, match on ref + pred + succ + type + lag.

## Formula trace version compatibility

- **v1** (`2026-07-02.phase0-cpm-formula-trace.v1`): `longest_path.diff_status = not_evaluated`; overall `pass_with_exclusions`.
- **v2** (`2026-07-02.cpm-longest-path-shadow.v2`): requires `longest_path.diff_status = pass` or `fail` unless `--allow-missing-longest-path` is supplied.
