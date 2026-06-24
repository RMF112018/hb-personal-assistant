# 306 — Forecast P10 PR2: correctness VALUE tests (gap-only)

- Status: accepted
- Date: 2026-06-24
- Phase: forecast-model remediation P10 (second of two PRs; PR1 = ADR 304, P10c = ADR 305)
- Gap: #10 (forecast-correctness & isolation test hardening)

## Context

P10 is the test-hardening phase of the forecast-model remediation. PR1 (#110) and the residual
green-up P10c (#111) drove `pytest -k forecast` to **0 failing** on `main @ 548d55d2`. P10's second
deliverable — the gap-validation report's "add tests that assert forecast VALUES given inputs" — is
the last open P10 piece.

A pre-implementation sweep of the existing suite found that **most of the spec's VALUE bullets are
already covered** by the P1/P2/P2b work and by CFR's native probability suite. Re-asserting them
would be pure duplication. The decision (recorded here) is **gap-only**: add tests only for the two
value behaviors that are genuinely unasserted, and **attest** the rest against the exact existing
tests rather than re-testing them.

The new tests additionally **surfaced a pre-existing production defect** — a connection leak in
`SQLiteMigrator.apply()` — which is fixed in this PR (see "Connection-leak fix" below). Apart from
that one-line store-layer fix, this PR is tests + docs only: no schema/count change, no live-DB write.

## Decision

Add `tests/test_forecast_correctness_values_p10.py` covering the two real gaps:

1. **Probability band VALUE correctness.** Existing tests only *count*-assert
   `forecast_output_probability` rows. The new tests project a probability package and assert the
   `p10/p50/p90` band values **round-trip exactly** (string-Decimal) through
   projection → `forecast_output_probability` → read layer, that `p10 ≤ p50 ≤ p90` holds, and that
   the repo reader (`output_repository.read_output_probability_from_db`, raw-json echo) and the
   business-safe read model (`ForecastRunReadModelService.read_output`, typed columns) both surface
   them.

2. **Second-project (non-tropical) VALUE isolation.** Every other main-repo value test uses
   `project_key="tropical"`; the only multi-project test merely checks pre-seeded rows survive a live
   write. The new tests run a distinct project (`"harbor"`) alongside `"tropical"` in the **same**
   temp DB and assert: each header aggregates only its own per-code costs (no cross-sum); the
   prior-run delta is project-scoped (a later-created tropical run is **not** picked up as harbor's
   prior — proven by delta value and `prior_run_id`); and `list_outputs(project_key)` filters
   correctly.

## Already-covered (attested, NOT re-tested)

| Spec VALUE bullet | Covered by |
|---|---|
| header == per-code Decimal sum (plan, persisted, read model, skip-missing) | `tests/test_forecast_output_projection_phase2a.py`: `test_header_aggregates_per_code_costs_in_plan`, `test_apply_persists_header_totals`, `test_header_aggregation_skips_missing_values_and_warns`, `test_readmodel_surfaces_header_totals` |
| prior-vs-current delta | `phase2a.py`: `test_prior_run_delta_and_current_vs_prior_change_row`, `test_first_run_has_no_prior_delta` |
| operator dollar value-override re-aggregation | `tests/test_forecast_output_overrides_p2b.py` (all 7) |
| assumption-consumption impact (confidence modifier + required gate; flag-off byte-identical) | `tests/test_forecast_assumptions_consume_p2.py` (all 6) |
| floor-to-actuals | CFR native suite: `test_fp_simulate.py::test_floor_at_actuals` / `::test_near_complete_codes_stay_at_actual`; `test_reconcile.py::test_reconcile_floors_to_actuals` / `::test_reconcile_weighted_and_floored` (`model_recommended_floored_to_actuals`); `test_fp_distributions.py::test_median_anchors_to_recommended_ctc` / `::test_near_complete_is_point_mass_at_actual` |

Note: the CFR floor tests run in CFR's own suite; their filenames do not match `-k forecast`, so they
are not visible in that filter. Per the gap-only decision this is accepted (floor logic lives in CFR
and is tested where it lives) rather than mirrored into the main repo.

## Connection-leak fix (`SQLiteMigrator.apply()`)

Running the full `-k forecast` suite with the new module **deterministically** failed an unrelated
canary, `test_forecast_model_controls_db_config_phase17.py::test_live_db_and_source_config_not_mutated`
(passed in isolation and without the new module; failed 3/3 with it). Root cause:
`store/migrator.py::SQLiteMigrator.apply()` opened two `get_connection()` connections (the migration
connection and a second one solely to read `MAX(version)`) and **closed neither** —
`get_connection`'s documented contract is that *the caller closes it*, and `transaction()` never
closes. The DB is `journal_mode=WAL`, so a leaked connection's `-wal` is checkpointed into the main
DB file only when Python GC finalizes it. The new tests changed GC/finalization timing enough that a
benign checkpoint (relocating `_setup`'s **own** writes from `-wal` to the main file — no new data,
read-only intent intact) landed during phase17's read-only `_run`, changing `db.read_bytes()`.

Fix: `apply()` now reads the version on the existing connection and **closes** it before returning
(eliminating both the migration-connection leak and the redundant second connection). This honors the
`get_connection` contract, removes a real resource leak on a universal DB-init path, and makes the
WAL checkpoint deterministic — so the canary passes without modifying the canary itself. This was the
minimal surgical fix (no re-indentation of the ~880-line migration body).

Note: `origin/main` independently added `scripts/test-forecasting.sh` / `scripts/test-schedule.sh`
(commit `8703f7c`), and the bundle docs **explicitly exclude** this canary as "a byte-for-byte SQLite
comparison that is not stable under the current local runtime" — corroborating the diagnosis. The
migrator fix is kept regardless: the byte-canary exclusion sidesteps the *symptom* in the fast bundle,
while the fix removes the *root-cause* leak that also affects full-suite/release validation. Because
`apply()` is universal (forecasting + schedule), the change was validated against BOTH bundles — the
schedule bundle exercises the migrator/schema-migration tests (`test_migrator_v64/v65/v70/v71`,
`test_schedule_schema_migration`), all green.

## Consequences

- `pytest -k forecast` gains 6 tests and stays at **0 failing** (purely additive).
- No production behavior changes; no new flags, schema, or table-count changes.
- The two previously-unasserted value invariants (band ordering/round-trip; cross-project isolation)
  now regression-guarded in the main repo.

## Validation

- New module green in isolation (`tests/test_forecast_correctness_values_p10.py`, 6 passed).
- Perturbation sanity check: temporarily corrupting an expected band value and an expected
  cross-project header each made the corresponding assertion fail (tests are non-vacuous), then
  reverted.
- Focused validation via the repo's fast bundles (preferred over the 20-min full suite):
  - `scripts/test-forecasting.sh` — 0 failing (incl. the 6 new tests; the new test file was added to
    the bundle's target list so the bundle covers it going forward).
  - `scripts/test-schedule.sh` — 0 failing; migrator/schema-migration tests green (cross-cutting
    proof for the `apply()` fix).
- `ruff check` clean on the new file.
