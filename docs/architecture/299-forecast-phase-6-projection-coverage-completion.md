# ADR 299 — Forecast Phase 6: projection coverage completion (commitment_exposure + schedule_phasing)

## Status

Accepted.

## Context

Two V63 output tables stayed `operational_empty_expected` after Phase 2c because their sources
didn't map 1:1. With clean single-source mappings now identified and the commitment-exposure
semantics decided, this phase populates both — completing the run-output projection layer. No
schema/migration/count change.

## Decision

Extend the existing read-only projector (`construction/forecast/output_projection_engine.py` +
`output_repository.py`) — mirroring the Phase-2c writer/reader/`_upsert` pattern — and wire the
two tables into the Phase-3 gated live-write.

- **commitment_exposure** ← context `canonical/budget_codes.jsonl` per-row `amounts` (BudgetDetails
  passthrough): `committed_amount = committed_costs`, `exposure_amount = committed_costs −
  commitment_invoiced` (Decimal, 2dp; null invoiced → 0). Emit only for codes with a non-null
  `committed_costs`. New optional `context_package` projector input.
- **schedule_phasing** ← `forecast_monthly_package` (already an input): join
  `schedule_monthly_phasing_by_budget_code.jsonl` with `monthly_forecast_by_budget_code.jsonl`. For
  rows with `used_for_budget_code_phasing == true` and a non-empty positive-weight distribution:
  `phase = schedule_association_type`, `start_month`/`end_month` = min/max weighted month,
  `amount = recommended_final_cost`. Not-used rows skipped.

Decimal-only math via `_money_2dp`/`_money_sub` (no floats). `raw_json` is deterministic so the
Phase-3 re-projection certification still matches.

**Phase-3 wiring** (`workflows/live_db_run_output_projection.py`): added the two tables to
`V63_TABLES` (so they are tropical-replaced + digest-certified in the gated live write) and threaded
a `context_package` param through `_build_temp_projection` (write-temp + cert-temp),
`run_controlled_live_db_run_output_projection`, and the `live-db-run-output-project` CLI.

## Consequences

- The run-output projection layer is complete (all V63 child tables populated from CFR artifacts).
- No schema/migration/count change ⇒ clean merge through the concurrent schedule churn.
- Read-model API + UI still surface budget_codes/risks/monthly/probability/changes/staffing;
  surfacing these two new arrays is a small follow-on (out of scope).
- No real live write performed (the authorized operator step is unchanged).

## Verification

- `tests/test_forecast_output_coverage.py` — commitment_exposure populates with
  `exposure == committed − invoiced` (1000.00 − 250.00 = 750.00); schedule_phasing populates
  (phase/start/end/amount; not-used rows skipped); idempotent; dry-run writes nothing.
- `tests/test_forecast_live_db_run_output_projection.py` — both tables written-tropical and
  post-write `certified` with the `context_package` fixture; CLI `--context-package`.
- Existing phase2a coverage unchanged; ruff clean on the touched `construction/forecast/` modules.
