# ADR 295 — Forecast Phase 2b: decision-support schema (V66) + read-only projector

## Status

Accepted.

## Context

The remediation's controlling principle is **maturity-aware, resilient to incomplete data**:
incomplete data should lower confidence and adjust method weighting/eligibility, not block a
run. Exploration confirmed the decision-support **logic already exists and is well-tested** —
it is just computed into files / on-demand reports and never persisted per-run into a
queryable DB schema:

- CFR `workflows/model_engines_readiness.py` — maturity tiers (`3/6/12` months) + coverage gates.
- CFR `forecast_accuracy/{confidence,estimators,signals}.py` — numeric confidence bands
  (`0.85/0.70/0.50/0.30`), evidence-depth (0–5), 5-estimator eligibility gates.
- CFR analysis package `confidence_rollup.json` + per-code `confidence` (already projected into
  V63 `forecast_output_budget_codes` in Phase 2a).
- hb_assistant `forecasting/readiness.py`, and `second_brain/financial_completeness.py` (the V35
  precedent of *persisting* readiness snapshots to DB).

The gap is **persistence + queryability, not computation**.

## Decision

Add the decision-support schema as **V66** and a **read-only engine** that derives
maturity/availability from the DB and projects the already-computed confidence — into a temp DB
only, never live — keyed to a forecast run. **No new scoring math**: reuse the existing
thresholds/values.

### Schema (V66, family `forecast_decision_support_v65`, all `operational_empty_expected`)

8 additive tables in `src/hb_assistant/store/forecast_decision_support_tables.py`, wired via
`SQLiteMigrator._v65_statements()`: `forecast_project_maturity_snapshots`,
`forecast_data_availability_profiles`, `forecast_method_eligibility`,
`forecast_model_selection_decisions`, `forecast_confidence_scorecards`,
`forecast_confidence_factors`, `forecast_operator_assumptions`,
`forecast_required_assumptions`. FK to `forecast_runs(run_id)` / `forecast_outputs(output_id)`;
V59/V63 column style (TEXT PKs, TEXT Decimal scores, `raw_json`). `table_count` → 433.

### Engine (read-only, temp-DB only)

`src/hb_assistant/construction/forecast/decision_support_engine.py` +
`decision_support_repository.py`:

- **Derives** maturity tier (M0–M5 from completed-month count, reusing the `3/6/12` thresholds —
  M5 closeout deferred until a lifecycle signal exists) and per-domain data availability from the
  V59 tables; domains without a V59 source table (owner/commitment/schedule/staffing) are recorded
  `unavailable` (a confidence penalty, not a block).
- **Projects** the project confidence scorecard from `confidence_rollup.json` and per-code
  scorecards from V63 `forecast_output_budget_codes`. Every scorecard emits ≥1 factor row (the
  persisted explanation — remediation §20).
- Refuses the live DB (`is_live_db_path`), reads inputs read-only, writes only on `apply` in one
  transaction; dry-run writes nothing; idempotent UPSERTs; optional parity (row-count) check.

**Deferred-empty this phase:** `forecast_method_eligibility`,
`forecast_model_selection_decisions`, `forecast_operator_assumptions`,
`forecast_required_assumptions` (their clean sources — the `forecast_accuracy` per-method artifact
and the operator UI — are a follow-on slice), mirroring Phase 2a's slice discipline.

## Consequences

- Maturity/availability/confidence are now persisted per-run and queryable; no behavioral change,
  no live write.
- Lifecycle bookkeeping: `table_count` 425 → 433; the ~18 hardcoded count asserts bumped in
  lockstep; the new migrator test is **self-consistent** (no hardcoded absolute) — a deliberate
  guard against the concurrent-schema-version churn observed in Phase 2a/V64.
- Reuses existing thresholds verbatim; introduces no new scoring math to re-validate.

## Verification

- `tests/test_migrator_v65_forecast_decision_support.py` — version, presence, empty, idempotency,
  prior-version preservation, FK, self-consistent lifecycle classification.
- `tests/test_forecast_decision_support_phase2b.py` — maturity tiers (M0/M1/M2/M4); absent domains
  `unavailable`; project scorecard from rollup with factors; per-code scorecards reuse V63
  confidence; dry-run writes nothing; apply refuses live DB; apply writes with parity and is
  idempotent.
