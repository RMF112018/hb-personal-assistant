# Forecast Improvement Audit — Architecture

Additive, advisory, read-only slice that validates the seven previously identified forecasting-priority
improvements against **repo truth + data truth** and implements each ONLY where the currently available
JSON packages / SQLite tables support it. It produces one timestamped package
`forecast_improvement_audit_package_tropical_<stamp>/` and never mutates an accepted/source/historical
package, Excel, or the SQLite DB (opened strictly read-only).

## Governance (authoritative)

- **CostEntries/Sage actual cost to date is the only hard FLOOR**, everywhere.
- **Reference values never cap NON-fee forecasts** (budget, current projected cost, revised budget, ERP,
  owner SOV, pay app, invoice, schedule, change order, historical forecast).
- **FEE codes ARE capped by the projected budget value, subject to the actuals floor.** Fee codes
  (currently `20-18-110 CONTRACTORS FEE`, config `fee_cost_codes`): the projected budget value
  (config `fee_cap_source_field`, default `projected_budget`) is the upper cap. If the evidence-supported
  fee exceeds it, cap at it; if actual fee cost already exceeds the cap, actuals control and an
  `actuals_exceed_fee_cap_exception` is emitted (never below actuals); a missing/zero cap value yields a
  data gap, never an invented cap. This carve-out is NOT a defect.
- Everything is advisory (`requires_human_acceptance: true`); proposed changes carry `do_not_auto_apply`.
  Nothing is applied into accepted outputs.

## Modules (`src/construction_financial_review/forecast_improvement_audit/`)

- `inputs_io.py` — discovers packages (reuses `forecast_comprehensive.package_discovery`) and loads every
  input surface read-only, including a strictly read-only (`mode=ro`) SQLite read of change orders +
  contracts and a schema/counts inventory. The build step is a pure function of the returned `inputs`.
- `decisions.py` — the 7-row `improvement_support_decisions` table + `data_inventory` + `sqlite_inventory`.
- `boe.py` — `BASIS_OF_ESTIMATE.md` for this package (14 required sections incl. governance) +
  `basis_of_estimate_coverage.json` scoring each existing package's doc coverage (follow-up only; no
  accepted package mutated).
- `calibration.py` — re-exposes the accepted accuracy backtest (MAPE + bias, per method + cohort) with
  denominator + sample-size guards; WAPE/MAE are NOT invented (reported as a data gap).
- `lag.py` — actual-cost lag risk by comparing CostEntries activity (trend evidence + amounts) vs leading
  indicators (sub invoices, schedule); never infers actual cost.
- `schedule_readiness.py` — schedule cost-loading readiness posture (`schedule_can_drive_phasing` /
  `…inform_phasing_only` / `…context_only` / `…not_usable`).
- `gcgr_fee.py` — GC/GR behavior classification + the **fee projected-budget cap** enforcement and
  follow-up flagging.
- `change_order.py` — change-order exposure classes from the DB (`approved_executed` / `pending_unsigned`
  / `potential_unapproved` / `void_rejected` / `unknown_status`), project/family-level mapping (no
  per-budget-code link in the DB), double-count risk vs current projected cost.
- `validation.py` — fail-closed gates, including the three distinct cap gates.
- `generate_forecast_improvement_audit_package.py` — orchestrator + `run()`; mirrors the
  `forecast_comprehensive` shape (pure `_build_collections`, frozen-stamp determinism check, manifest,
  README/SCHEMA/BOE, audit/* and source-hash integrity).

## Validation gates (fail-closed; `passed = all(checks)`)

Three distinct cap gates encode the corrected governance:

- `no_reference_caps_for_non_fee_codes` — no non-fee diagnostic row carries a truthy `*_cap_applied`.
- `fee_projected_budget_cap_enforced` — fee rows are capped at the projected-budget value where it exists;
  a missing cap value must be a data gap (`fee_cap_missing_value_reported_as_gap`), not an invented cap.
- `actuals_floor_preserved` — every emitted fee final-cost ≥ actual fee cost to date.

Plus: all files parse, deterministic quant core (frozen stamp), source hashes unchanged, SQLite read-only
+ no mutation, no external calls, no historical forecast as actual, advisory fields present, calibration
guards present, schedule posture present, data gaps not silently skipped, every decision evidence-linked,
BOE present, safety scan passed.

## Determinism

`inputs_io.load_inputs` reads every source (packages + DB) once; `_build_collections` is a pure function
of `inputs`, so the two-build determinism check is byte-identical for the quantitative core (env/path
audits — `source_files_used`, `db_inventory`, `source_hashes_before_after`, manifest, validation report —
are excluded from the byte diff). The DB is read once up front; no `datetime.now`/randomness in the build.

## Decisions (current data cycle)

| # | Improvement | Decision |
|---|---|---|
| 1 | FHI prior-evidence layer | `implemented_and_validated` (audit-only; 4 hardening items confirmed in code + tests) |
| 2 | Basis of Estimate | `newly_implemented` (this package + coverage audit) |
| 3 | Backtesting / calibration | `partially_supported_diagnostic_only` (MAPE + bias only; small cohort) |
| 4 | Actual-cost lag diagnostics | `newly_implemented` |
| 5 | Schedule cost-loading readiness | `newly_implemented` (mapping sparse → inform/context posture) |
| 6 | GC/GR + fee cap | `newly_implemented` (fee cap proven in-audit; upstream enforcement = follow-up) |
| 7 | Change-order exposure | `newly_implemented` (project/family-level; no per-code DB link) |

## Out of scope / follow-ups

- No consumer/decision-ledger slice; the fee cap is proven here but NOT applied into accepted outputs — a
  future slice applies it with explicit authorization.
- BOE for existing packages = coverage diagnostic + documented follow-up only.
