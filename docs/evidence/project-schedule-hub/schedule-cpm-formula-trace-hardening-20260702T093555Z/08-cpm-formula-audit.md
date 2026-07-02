# CPM formula audit

- schedule version: `tropical|1|2026-06-01 08:00`
- chain id: `8e34955ca2691580`
- formula version: `2026-07-02.phase0-cpm-formula-trace.v1`
- diff status: **pass_with_exclusions**
- activities traced: 2
- relationships traced: 1
- matched activities: 2
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
  --schedule-version-key tropical|1|2026-06-01 08:00 \
  --latest \
  --out-dir <evidence-dir>/cpm-formula-trace
```
