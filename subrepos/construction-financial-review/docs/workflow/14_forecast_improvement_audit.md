# Workflow 14 — Forecast Improvement Audit

Additive, advisory, read-only audit of the seven forecasting-priority improvements. Run it after the
accepted context / accuracy-next / monthly / probability / history packages exist; it discovers and reads
them (and the read-only SQLite DB) and emits one audit package. It never mutates anything and never
applies a change into an accepted output.

## Run

```bash
cd subrepos/construction-financial-review
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-improvement-audit \
    --project tropical --frozen-stamp 20260101_000000 --out-root /tmp/fia
```

Omit `--frozen-stamp` / `--out-root` for a live timestamped package under the data root. The run is
read-only against every source surface; the SQLite DB is opened strictly `mode=ro`.

## What it produces

`forecast_improvement_audit_package_tropical_<stamp>/`:

- `improvement_support_decisions.json` — the 7-row decision table (decision, evidence, data fields,
  limitations, validation/tests, advisory flag).
- `data_inventory.json` / `sqlite_inventory.json` — discovered packages + read-only DB schema/counts.
- `BASIS_OF_ESTIMATE.md` + `basis_of_estimate_coverage.json` — BOE for this package (14 required sections
  incl. governance) + per-package doc coverage (follow-up only).
- `calibration_enhancements.jsonl` — method/cohort MAPE + bias with `insufficient_sample` +
  `mape_denominator_valid` guards (WAPE/MAE not invented).
- `actual_cost_lag_diagnostics.jsonl` — `lag_classification` + `lag_flags` (no inferred actual cost).
- `schedule_cost_loading_readiness_audit.json` — `recommended_posture`.
- `gcgr_behavior_diagnostics.jsonl` — GC/GR behavior class (advisory; never changes final cost).
- `fee_cap_diagnostics.jsonl` — `fee_projected_budget_cap_value`, `evidence_supported_fee_before_cap`,
  `fee_forecast_after_cap`, `fee_projected_budget_cap_applied`, `actuals_exceed_fee_cap_exception`,
  `fee_cap_basis` (`projected_budget_value` | `none`).
- `change_order_exposure_evidence.jsonl` (+ `change_order_exposure_summary.json`) — exposure classes +
  double-count risk (project/family-level; no per-budget-code DB link).
- `improvement_data_gaps.jsonl` — valid-but-unsupported pieces + required follow-ups.
- `validation_report.json`, `manifest.json`, `README.md`, `SCHEMA.md`, `input_inventory.json`,
  `audit/*` (improvement coverage, cap-governance scan, source files, db inventory, safety, source hashes).

## Governance

- CostEntries/Sage actuals are the only floor. Reference values never cap NON-fee forecasts.
- FEE codes (currently `20-18-110 CONTRACTORS FEE`) ARE capped by the projected budget value, subject to
  the actuals floor; a missing cap value is a data gap, never an invented cap.
- Validation distinguishes `no_reference_caps_for_non_fee_codes`, `fee_projected_budget_cap_enforced`,
  and `actuals_floor_preserved`.
- The fee cap is proven in this audit's own logic only; no upstream generator enforces it yet — that is a
  recorded `required_follow_up_implementation` for a future consumer slice (with Bobby's authorization).

## Verify

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_fia_*.py
# validation_report.json -> "passed": true; two runs with the same frozen stamp are byte-identical (quant core)
```
