# P10 PR2 — forecast-correctness VALUE tests (gap-only) + migrator leak fix

- Phase: forecast-model remediation P10 (second of two PRs; PR1 #110, P10c #111)
- Branch: `feature/forecast-correctness-values-p10-pr2` off `origin/main @ 548d55d2`
- ADR: 306
- Scope: tests + docs, plus one store-layer production line (`SQLiteMigrator.apply()` leak fix
  that the new tests surfaced). No schema/table-count change. No live-DB write.

## What shipped

1. **`tests/test_forecast_correctness_values_p10.py`** (6 tests) — closes the two genuinely
   unasserted forecast VALUE behaviors:
   - **Probability band value-correctness** — `p10/p50/p90` round-trip exactly through projection →
     `forecast_output_probability` → read layer; `p10 ≤ p50 ≤ p90` ordering; surfaced via both
     `output_repository.read_output_probability_from_db` (raw-json echo) and
     `ForecastRunReadModelService.read_output` (typed). Prior tests only *count*-asserted these rows.
   - **Second-project (non-tropical, `harbor`) value isolation** — per-project header aggregation
     (no cross-sum); project-scoped prior-run delta (a later-created `tropical` run is NOT picked up
     as `harbor`'s prior — proven by delta value and `prior_run_id`); `list_outputs` project filter.

2. **`SQLiteMigrator.apply()` connection-leak fix** (`src/hb_assistant/store/migrator.py`) — see ADR
   306 "Connection-leak fix". The new tests deterministically surfaced a pre-existing leak (two WAL
   `get_connection()` connections never closed) that flipped phase17's raw-byte canary via GC-timed
   WAL checkpointing. `apply()` now closes the connection before returning. Benign root cause
   (read-only intent was never violated); fix makes the WAL checkpoint deterministic and the canary
   passes without modifying the canary.

## Already-covered (attested in ADR 306, not re-tested)

header == per-code Decimal sum + prior-delta (`phase2a`); operator dollar-override re-aggregation
(`p2b`); assumption-consumption (`assumptions_consume_p2`); floor-to-actuals (CFR
`test_fp_simulate`/`test_reconcile`/`test_fp_distributions`).

## Validation (repo fast bundles — preferred over the 20-min full suite)

After incorporating `origin/main` (FF to `8703f7c`, which added the bundles):

- `tests/test_forecast_correctness_values_p10.py` — 6 passed (isolation + under the bundle env).
- Perturbation sanity check (reverted) — the band-value and cross-project-header assertions both
  fail when their expected values are corrupted → non-vacuous.
- `scripts/test-forecasting.sh` — **0 failing** (incl. the 6 new tests; phase17 byte-canary excluded
  by the bundle by design). The new test file was added to the bundle's target list.
- `scripts/test-schedule.sh` — **0 failing**; migrator/schema-migration tests green
  (`test_migrator_v64/v65/v70/v71`, `test_schedule_schema_migration`) → cross-cutting proof that the
  `apply()` connection-close does not regress migration/schedule paths.
- `ruff check` clean on the new test file.
- Full default suite NOT run (per the bundle-first directive). See `regression_summary.txt` for the
  earlier `-k forecast` run (0 failing) and the investigation trail.

## Files

- `tests/test_forecast_correctness_values_p10.py` (new)
- `src/hb_assistant/store/migrator.py` (apply() closes its connection — leak fix)
- `scripts/test-forecasting.sh` (added the new test file to the bundle target list)
- `docs/architecture/306-forecast-p10-pr2-correctness-values.md` (new)
- `docs/forecasting/remediation/REMEDIATION-PLAN.md` (P10 row → merged; P10c → merged #111; PR2 row + changelog)
- this evidence bundle
