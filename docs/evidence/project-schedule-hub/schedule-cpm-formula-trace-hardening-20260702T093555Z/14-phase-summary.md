# Phase summary — CPM formula trace evidence hardening

## Result

Phase-0 CPM formula trace export is implemented and validated on a minimal XER fixture DB under `local-sensitive/clean-db/`.

## Fixture proof

- **diff status:** `pass_with_exclusions` (longest path excluded by design)
- **activities:** 2 traced, 0 mismatches
- **relationships:** 1 traced, 0 mismatches
- **source-field exclusion:** pass
- **export exit code:** 0

## Tests

- Focused: 18 passed (`test_schedule_cpm_shadow_formula_evaluator.py`, `test_schedule_cpm_formula_trace_export.py`)
- Regression: schedule import / CPM observability / clean-db phase-0 / db_path_guard — passed (see `10-regression-tests.txt`)

## Safety

- Live DB not touched
- Fixture DB under `local-sensitive/clean-db/` only (not committed)
- Mutation-proof row-count assertions in export tests

## Ready for full 14-stage clean-DB validation?

**Yes, with documented exclusions** (longest-path shadow replay deferred).

## Recommended next step

Run full clean-DB workflow validation using copied DB + formula trace export on TWNU package fixture after phase-0 purge/schema gates pass.
