# CPM formula audit

- schedule version: `tropical|1071|2026-06-23 08:00`
- chain id: `3f2756bfe3aa2368`
- formula version: `2026-07-02.phase0-cpm-formula-trace.v1`
- diff status: **pass_with_exclusions**
- activities traced: 1507
- relationships traced: 3921
- matched activities: 1507
- mismatched activities: 0

## Source-field exclusion

- status: pass

## Longest path

- Longest-path independent replay not implemented in this hardening pass.

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
