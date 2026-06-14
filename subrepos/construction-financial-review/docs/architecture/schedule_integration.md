# Architecture — Schedule-Integrated Forecast Slice

## Purpose

Add a durable, config-driven feature that consumes the P6/XER-derived schedule package and layers
schedule-derived **timing / remaining-work / sequencing / risk** evidence onto the crosswalk-v2
forecast recommendations. Schedule data is never accounting actual cost and never an independent
cost driver.

## Module layout

`src/construction_financial_review/schedule_analysis/`

| Module | Responsibility |
|--------|----------------|
| `schedule_io.py` | Package discovery; streaming readers; pure normalizers (status, cost-code, dates, durations, float, milestone). |
| `schedule_mapping.py` | Canonical cost-code → `budget_code_key` resolution. Canonical BudgetDetails is the sole authority; extractor candidates are supporting evidence only; multi-category cost codes stay `ambiguous`. |
| `schedule_rollup.py` | Activity-level forecast features (Phase 4) and per-budget-code rollup (Phase 5) with remaining-work classification and schedule-only risk level. |
| `forecast_integration.py` | Deterministic `actuals_near_projected` (0.90), Phase-9 action rules (preserve increase, block decrease, strengthen review, exhaustion → review), and Phase-6 alignment rows. |
| `cashflow.py` | Duration-weighted month allocation of remaining exposure (timing only; confidence capped at medium; ties to exposure). |
| `generate_schedule_integrated_forecast.py` | Orchestrator: load → map → roll up → integrate → cash-flow → risk/review → write package + manifest + validation + safety + git metadata. |

Reuses the existing `common/` library (`io`, `money`, `dates`, `hashing`, `safety`, `validation`,
`budget_keys`) — no duplication of JSONL/Decimal/manifest/safety helpers.

## Data flow

```
schedule_activities.jsonl ─┐
canonical/budget_codes.jsonl ─► schedule_mapping (canonical authority)
                              └► features + rollup (per 127 keys)
crosswalk_v2 recommendations ─► forecast_integration ─► schedule-integrated recommendations (127)
                                          │
                                          ├► alignment (127)  ├► schedule risk register
                                          └► cashflow timing curve (timing only)
```

## Determinism & safety

- All JSONL sorted by primary key; money via `Decimal(str(...))`; no floats for money.
- A `--frozen-stamp` produces a byte-identical package (verified by full recursive diff, incl.
  manifest sha256s).
- `validation_report.json` gates: one row per canonical key, all keys canonical, no schedule-only
  numeric increase, decreases blocked where material, cash-flow ties to exposure, no fuzzy mapping,
  mapped keys canonical, safety scan passed.

## Integration point

CLI subcommand `schedule-integrate-forecast` (import-dispatched, config-driven) in `cli.py`; project
config keys `schedule_package` and `forecast_analysis_package_crosswalk_v2` in
`config/projects/tropical.json`.
