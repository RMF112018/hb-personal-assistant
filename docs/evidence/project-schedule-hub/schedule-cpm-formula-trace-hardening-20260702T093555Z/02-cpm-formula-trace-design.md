# CPM formula trace design

## Version

`2026-07-02.phase0-cpm-formula-trace.v1`

## Triple diff

Each traced field records:

- `persisted_result` — value from lineage-resolved CPM run rows
- `engine_recomputed_result` — pure `compute_*` replay on canonical activities/relationships
- `shadow_formula_result` — independent evaluator with explicit formula strings

Mismatch gates: `match_persisted_vs_engine`, `match_engine_vs_shadow`, `match_persisted_vs_shadow`.

## Shadow evaluator

`CpmShadowFormulaEvaluator` implements FS/SS/FF/SF forward/backward, total float (`LS-ES`), per-type free float, and criticality thresholds. Candidate selection records **rejected candidates** and tie-break rules.

## Lineage resolution

`CpmRunChainResolver.resolve(latest=True)` selects the newest terminal criticality run and walks `source_run_id` — never mixing per-stage “latest” runs.

## Structured exclusions

- Longest path: `diff_status=not_evaluated`, overall `pass_with_exclusions`
- Source float/critical fields: structured `source_field_exclusion` gate in diff JSON

## Outputs (5 files)

1. `cpm-run-summary.json`
2. `cpm-activity-formula-trace.jsonl`
3. `cpm-relationship-formula-trace.jsonl`
4. `cpm-validation-recompute-diff.json`
5. `cpm-formula-audit.md` (PM-safe; technical JSON/JSONL allowlisted)

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | pass / pass_with_exclusions (or `--allow-mismatches`) |
| 1 | formula diff mismatch |
| 2 | CLI / live-DB / clean-copy guard |
| 3 | incomplete / invalid lineage |
| 4 | export I/O failure |

## Safety

- Read-only SQLite URI for row-count snapshots
- `assert_not_live_db` + `local-sensitive/clean-db/` guard
- Mutation-proof tests assert unchanged row counts
