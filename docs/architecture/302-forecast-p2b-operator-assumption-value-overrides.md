# ADR 302 — Forecast P2b: operator-assumption dollar value-overrides

## Status

Accepted.

## Context

P2 (ADR 301, PR #107) made operator assumptions affect the forecast's **confidence** scoring and
added a required-assumption gate, but deferred **dollar value-overrides** — letting an operator
assumption change a budget code's projected cost / cost-to-complete (and therefore the EAC/CTC
header totals). The deferral was deliberate: it needs (1) a reserved `assumption_type` convention
to turn a free-text assumption into a typed dollar override, and (2) care with P1's header
aggregation, which sums the **raw** recommendation rows.

Constraints confirmed from code:
- `plan_run_output_projection` is **DB-free by contract** — like P2, overrides must be read
  read-only from the live managed DB and **pre-hydrated** into the planner.
- The P1 header aggregation sums the raw `rec_rows`, so overrides must feed the aggregation.
- `_prove_parity` and every `read_output_*_from_db` reader compare/return **`json.loads(raw_json)`
  only** — so overriding the **typed columns** while keeping each row's `raw_json` as the original
  source recommendation is fully parity-safe. The overridden header columns are not in raw_json
  (P1 kept totals out), so header parity is unaffected too.
- `_augment_prior_deltas` runs in the apply path after planning, reading the header EAC — so
  planner-applied overrides are automatically reflected in the prior-run delta.

## Decision

Apply operator dollar overrides in `output_projection_engine`, behind a **separate** default-off
flag (value-overrides mutate real dollars — higher-stakes than P2's confidence factors — so they
are opted in independently).

- **Reserved `assumption_type`s:** `projected_cost_override` → `recommended_projected_cost`;
  `cost_to_complete_override` → `recommended_cost_to_complete`. Each requires a non-null
  `budget_code_key` matching a recommendation row and a value parseable by `_money_2dp` (Decimal,
  TEXT not float). Null-key / unmatched / unparseable overrides are **skipped with a warning**
  (never applied project-wide). Degraded-not-fatal.
- **Guarded post-pass in the planner** (`plan_run_output_projection` gains a pre-hydrated
  `operator_assumptions` param): runs only when ≥1 valid override exists, so the no-override path —
  including the P1 aggregation — is byte-identical. When overrides apply it sets the matching
  per-code **typed column** (raw_json untouched), re-aggregates the header EAC/FAC/CTC/variance from
  the effective per-code values (`budget_amount` sum unchanged), and appends one
  `operator_value_override` change row per override (deterministic id
  `foch-<hash(output_id|key|operator_value_override)>`, `delta_amount = override − original`) for
  audit — the same parity-safe `changes`-row pattern P1's `current_vs_prior` row uses.
- **Read bridge** (`project_run_output` gains `assumptions_db_path`): when
  `resolve_assumption_overrides_enabled()` is true, a private `_hydrate_operator_assumptions` helper
  reads operator assumptions **read-only (`mode=ro`)** from the live managed DB (or an explicit path
  for tests) via the existing `assumptions_repository.read_operator_assumptions_from_db`, and threads
  them into the planner — in both dry-run and apply paths (so a dry-run previews the effect). The
  planner never opens that connection itself; `assumptions_repository.py` stays a pure
  conn-accepting reader module.
- **Flag** `HB_FORECAST_ASSUMPTION_OVERRIDES_ENABLED` (default OFF) + resolver + settings
  persistence, mirroring P2's `assumption_consumption_enabled` trio. Like P2's flag it is not
  surfaced in `build_runtime_status` (admin visibility can follow once validated).

No schema/migration/v66+ change (override values are TEXT into existing nullable columns; the
`operator_value_override` change row uses the existing `change_type`). No live-DB write (overrides
read is `mode=ro`; the `is_live_db_path` write-guard on `db_path` is untouched). No decision-support,
run-service, CLI, or UI change.

## Consequences

- Operator assumptions can now move the actual forecast dollars (per-code projected cost /
  cost-to-complete → EAC/CTC header → prior-run delta), with a full audit trail in the `changes`
  table and the original source recommendation preserved in `raw_json`. This completes the
  operator-assumptions consumption story (confidence in P2, dollars in P2b).
- The override convention is intentionally narrow (two reserved types, per-code, explicit value).
  Broader override semantics (project-level, percentage, category-scoped) are out of scope.
