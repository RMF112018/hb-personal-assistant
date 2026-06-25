# 317 — Forecast generation: package-free DB-native generation engine

- Status: accepted
- Date: 2026-06-25
- Phase: Forecast Run Center remediation — Phase E (DB-native generation engine)
- Related: ADR 316 (DB-native context builder), ADR 315 (DB-native source snapshot),
  ADR 314 (DB-native contract & routing boundary), ADR 313 (DB-native boundary, fail-closed)

## Context

Phases B–D built the DB-native path up to a typed, in-memory `DbNativeForecastContext` (financial
spine) but nothing turns that context into a **forecast result**: the route is fail-closed end to end.
The CFR generators (`forecast_comprehensive` / `forecast_monthly` / `forecast_probability` /
`forecast_model_controls`) are package-coupled — they discover and consume upstream package
directories and emit ~30-file package outputs. Phase E adds a **package-free generation engine** that
consumes the Phase D context and produces a typed, in-memory result object — the seam Phase F persists.

The deterministic heart of `forecast_comprehensive` is `forecast_cost_basis.classify` + `apply`
(per-code dict in → final cost / cost-to-complete out: actuals floor, asymmetric raise, dormancy
suppression). That logic is genuinely package-free, so Phase E **reuses it** rather than reimplementing
a cost formula.

## Decision

Add `generation/db_native_generation_engine.py` (pure CFR; **imports no `hb_assistant`**; no package
files, no `run_lineage`, no `package_resolution`, no package workflows):

- `DbNativeGenerationEngineInput` — `project_key`, `generator_kind`, `forecast_window`, and the Phase D
  `DbNativeForecastContext`.
- `generate_db_native_forecast(inp) -> DbNativeForecastResult` dispatches on `generator_kind`:
  - `comprehensive` → financial-spine forecast (below).
  - `monthly` / `probability` / `model_controls` → an **honest unsupported result** (status
    `unsupported`, curated per-kind code, no forecast values, no package fallback).
  - any other kind → `db_native_unknown_generator_kind`.
- `DbNativeForecastResult.public()` is the redaction-safe contract: `status`, `result_code`,
  curated `message`, `generation_scope`, `forecast_window`, `maturity`/`confidence` (surfaced from the
  context readiness, **not recomputed**), per-code `forecast_lines`, `summary`, `assumptions`, `risks`,
  `unsupported_outputs`, `warnings`, `blockers`, `provenance`. No paths, package names, `raw_json`, raw
  exceptions, or secrets.

`comprehensive` (financial-spine only):

- Per budget code, map the spine's `budget_amounts` + `actuals` into the canonical
  `forecast_cost_basis.apply_cost_basis_decision(...)` inputs and reuse the established rules. Money is
  Decimal throughout; **final cost never falls below actual cost to date**; `cost_to_complete =
  max(final − actual, 0)`.
- Missing-vs-zero preserved: an explicit `"0.00"` is a real zero; a budget code with **no** budget
  amounts **and** no actuals yields a coded degraded row (`row_status=degraded_no_basis`,
  `forecast_final_cost=None`) — never a fabricated value.
- Overall status: `insufficient_basis` if no code yields a value; `generated_degraded` if readiness is
  sparse or any degraded rows exist; otherwise `generated`.
- Owner / Procore / owner-crosswalk evidence is **not yet DB-native**, so it is not used; the result
  carries an explicit `owner_procore_crosswalk_evidence_unavailable_financial_spine_only` warning and
  `unsupported_outputs` disclosing the three kinds it does not produce.

HB-side bridge `forecast_db_native_engine_adapter.compute_db_native_forecast(...)` runs the read-only
chain `build_db_native_source_snapshot → context_input_from_snapshot_public → build_db_native_context →
generate_db_native_forecast` and returns `result.public()`. It is the **only** HB→CFR bridge (the CFR
engine imports no `hb_assistant`), imports CFR lazily, reads the DB read-only, and mutates nothing.

## DB-native-unsupported is a valid honest terminal state

`monthly` / `probability` / `model_controls` are **not** failures of this implementation — their
required input families are not yet represented in the DB-native snapshot/context contract (phasing /
trend signals; Monte-Carlo simulation inputs; operator model-control config). The correct behaviour is
to return a specific curated code and produce **no** values. A later agent must **not** "fix" these
statuses by inventing values; they become supported only once their input families are DB-native.

## Cost-basis behaviour on the financial spine (repo-truth)

The DB-native spine carries `committed_costs` and `projected_costs` but **not** `erp_direct_costs` /
`pending_cost_changes`. The projected-cost *formula* (`committed + erp_direct + pending == projected`)
therefore cannot reconcile, and the canonical rules behave as follows — all honest, none fabricated:

| Spine condition | `cost_basis_status` | Final cost |
|---|---|---|
| committed cost present (formula cannot reconcile) | `manual_review_required` | inbound projected, **floored to actual**, flagged for review (no synthesised raise) |
| projected < actual | `existing_model_basis` (floor) | actual cost to date |
| committed `0.00` + no remaining evidence | `suppressed_no_remaining_commitment` | actual cost to date |
| no committed cost, basis present | `existing_model_basis` | projected / EAC / revised, floored to actual |
| no budget amounts and no actuals | `insufficient_row_basis` (degraded) | `None` |

The **asymmetric BudgetDetails raise** and **dormancy / operator suppression** require input families
not yet DB-native (ERP direct-cost breakdown; dormancy classification; operator controls), so they are
not reachable on the Phase E spine. The preserved safety property is the formula-guard: a
present-but-non-reconciling formula never yields a synthesised projected basis.

## Consequences

- A typed, package-free forecast result exists for Phase F to persist directly to the DB.
- The DB-native path takes no package dependency: no `SRC_FILES`, no package dir read/write, no
  `run_lineage`, no silent package fallback. `find_redaction_leaks(result.public()) == []`.
- The legacy package-backed generators are unchanged (their existing tests pass unmodified).
- The route `POST /api/forecast/runs/db-native` is **unchanged and still fail-closed**
  (`db_native_generation_not_implemented`); the adapter is tested but not route-wired.

## Persistence requirements for Phase F

- Map `result.forecast_lines` → `output_projection_engine` `budget_codes`/`outputs` rows; `summary` →
  the `outputs` header (`estimated_final_cost` / `forecast_at_completion` / `cost_to_complete` /
  `variance_*`); `risks` → `risks`; `assumptions` → `narratives` / `factors`.
- `output_projection_engine.project_run_output` currently takes **package Paths**; Phase F must add a
  package-free persist entry that accepts the in-memory result (or builds the plan dict directly),
  retaining the live-DB guard, the temp-DB requirement, and parity.
- Phase F then wires `route → adapter → persistence → certified output` and replaces the route's
  fail-closed seam.

## Non-goals (deferred)

- True DB-native `monthly` / `probability` / `model_controls` (await their DB-native input families).
- DB-native projection of the ERP direct-cost / pending-cost-change breakdown so the projected-cost
  formula can reconcile and the asymmetric raise becomes reachable.
- Output persistence, certification, prior-run storage, UI wiring, byte-parity with legacy packages.

## Guardrails

- No live-DB mutation; no external/LLM calls; no UI change; no output persistence in Phase E.
- New CFR engine imports no `hb_assistant`; the HB adapter is the only bridge. No schema / v60 / table
  count change; no `hb_assistant` schema change. Legacy generators untouched.
