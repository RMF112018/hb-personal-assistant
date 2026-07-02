# CPM formula audit

- schedule version: `tropical|1071|2026-06-23 08:00`
- chain id: `3f2756bfe3aa2368`
- formula version: `2026-07-02.cpm-longest-path-shadow.v2`
- diff status: **pass**
- activities traced: 1507
- relationships traced: 3921
- matched activities: 1507
- mismatched activities: 0

## Source-field exclusion

- status: pass

## Longest path

- algorithm: `repo_mirrored_shadow_dag_longest_path`
- path duration basis: path_finish_offset_days minus path_start_offset_days on the backtraced path (not sum of activity durations)
- diff status: **pass**
- persisted paths: 1
- shadow paths: 1
- matched paths: 1
- mismatched paths: 0

## Version compatibility

- v1 exports may show `longest_path.diff_status = not_evaluated` and overall `pass_with_exclusions`.
- v2 requires `longest_path.diff_status = pass` or `fail` unless `--allow-missing-longest-path` is supplied.

## Conclusion

Formula trace export completed for operator review. This report does not assert contractual schedule authority.

## Reproduce

```bash
python scripts/dev_schedule_cpm_formula_trace_export.py \
  --db-path <copied-db> \
  --schedule-version-key tropical|1071|2026-06-23 08:00 \
  --latest \
  --out-dir <evidence-dir>/cpm-formula-trace
```
