# ADR 301 — Forecast P2: consume operator assumptions (confidence + required gate)

## Status

Accepted.

## Context

ADR 300 shipped the first interactive write surface for forecasting: operators capture
`forecast_operator_assumptions` and `forecast_required_assumptions` (V66) through the Run
Center. Those tables were **written but never consumed** — no forecast computation read them,
so operator inputs had zero effect on a forecast. This is gap 2 of the forecast-model
remediation (severity: high; ledger `docs/forecasting/remediation/REMEDIATION-PLAN.md`, P2).

Two facts shape the design:

- **Assumptions live in the live managed DB.** The ADR-300 write surface persists them
  directly into the managed DB (`run_id` deliberately `NULL` → project-scoped). The forecast
  engines, by contrast, run against **isolated temp DBs** and fail-closed refuse the live DB
  for their run/write path (`is_live_db_path`). Reading assumptions from the engine's own
  `db_path` would therefore find zero rows.
- **An operator assumption is free-text.** `assumption_type` + TEXT `value` + optional
  `budget_code_key`. Turning one into a dollar override of a specific code's projected cost
  needs a reserved-type convention that is a product decision, not yet blessed.

## Decision

Consume operator assumptions in `decision_support_engine` (which owns confidence/scorecards)
as **confidence modifiers** + a **required-assumption satisfaction gate**, behind a default-off
flag. Dollar value-overrides are explicitly deferred to **P2b**.

- **Read bridge (read-only, pre-hydrated).** New consume-only
  `construction/forecast/assumptions_repository.py` reads the V66 tables; every query filters
  `WHERE project_key = ? AND run_id IS NULL` (the table's `UNIQUE(run_id, assumption_type)`
  does not dedupe NULL run_ids). `project_decision_support` reads the assumptions **read-only**
  (`mode=ro`) from the live managed DB — or an explicit `assumptions_db_path` (tests point this
  at a seeded temp DB) — and passes them as pre-hydrated lists into `plan_decision_support`.
  The planner never opens the assumptions connection itself, keeping it DB-decoupled and unit-
  testable. The `is_live_db_path` write-guard is unchanged and still applies only to the
  run/write `db_path`; the assumptions read is a separate `mode=ro` connection.
- **Confidence modifiers.** Each operator assumption's `confidence_impact`
  (`raises → booster`, `lowers → penalty`, `neutral → neutral`; absent → skipped) emits one
  ordinary confidence **factor** (`factor_key = operator_assumption:<type>`) on the matching
  scorecard — the per-code scorecard when `budget_code_key` resolves to one, else the project
  scorecard.
- **Required-assumption gate.** Each unsatisfied required assumption emits a project-scorecard
  `penalty` factor (`required_assumption_unsatisfied:<type>`) plus a `warnings` entry.
- **Degraded-not-fatal.** A missing/unreadable assumptions DB, or a factor with no scorecard to
  attach to, is recorded as a warning — never a failure.
- **Flag.** `HB_FORECAST_ASSUMPTION_CONSUMPTION_ENABLED` (default OFF), resolved by
  `resolve_assumption_consumption_enabled` in `forecast_runtime_config.py` (explicit > env >
  settings-file > False), mirroring `db_config_run_enabled`. Flag OFF (or no assumptions) ⇒
  planner output is byte-identical to before.

No schema/migration/lifecycle-count change (V66 tables already exist; factors persist via the
existing `apply_plan` → `upsert_confidence_factor`). No live-DB write (assumptions read is
`mode=ro`). `decision_support_engine`/`forecast_runtime_config` are pre-existing legacy files
that already fail `ruff format` on main and are not format-gated — edits match the surrounding
hand-style and are not wholesale-reformatted; the new reader conforms to `ruff format`.

## Consequences

- Operator assumptions now measurably affect confidence scoring and surface an explicit gate
  on unsatisfied required inputs — the P2 gap is closed for the confidence/gate dimension.
- **Deferred to P2b:** dollar value-overrides of per-code projected cost / cost-to-complete in
  `output_projection_engine` (needs a reserved `assumption_type` override convention and a
  header-aggregation re-run, since P1's `_money_sum` aggregates from the raw recommendation
  rows). Run-service orchestration is unchanged (it drives the CFR subprocess generator, not
  these engines).
