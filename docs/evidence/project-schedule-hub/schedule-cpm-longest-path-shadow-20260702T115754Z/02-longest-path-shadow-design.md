# Longest-path shadow design

## Shadow evaluator

- Module: `schedule_cpm_shadow_formula_evaluator.py`
- Method: `CpmShadowFormulaEvaluator.evaluate_longest_path()`
- Algorithm id: `repo_mirrored_shadow_dag_longest_path`
- Does **not** call production `compute_longest_path()` in the export path.

## Path duration

`path_duration = path_finish_offset_days - path_start_offset_days` on the backtraced path (not sum of activity durations).

## Diff statuses

| Status | Meaning |
|--------|---------|
| `pass` | Shadow matches persisted primary path |
| `fail` | Computed but mismatched |
| `not_computable_no_terminal_activity` | No valid end activity |
| `not_computable_empty_graph` | Empty activity set |
| `missing_required_longest_path_rows` | LP stage expected but persisted rows absent (strict default) |
| `allowed_missing_longest_path` | Same, with `--allow-missing-longest-path` |

## Version compatibility

- **v1** (`phase0-cpm-formula-trace.v1`): `longest_path.diff_status = not_evaluated`; overall `pass_with_exclusions`.
- **v2** (`cpm-longest-path-shadow.v2`): requires `longest_path.diff_status = pass` or `fail` unless `--allow-missing-longest-path`.

## Export artifacts

Six files including `cpm-longest-path-formula-trace.jsonl`.
