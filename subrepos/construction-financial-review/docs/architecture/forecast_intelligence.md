# Forecast Intelligence (next-gen anticipated-final-cost projection)

Status: current. Module: `src/construction_financial_review/forecast_intelligence/`.
CLI: `forecast-intelligence`. Output: `forecast_accuracy_next_package_tropical_<stamp>/`.

## Why this exists

The earlier `forecast_accuracy` slice produces an advisory model number that hugs a central blend,
gates its burn estimator off for near-complete codes, and never states an authoritative anticipated
final cost. It could not reliably **project budget-code-level overruns**. This slice does: it projects
the real anticipated final cost per canonical budget code (127 for Tropical) and surfaces overruns,
using schedule-remaining-work and recent-trend evidence.

## Core principle (uncapped)

Actual cost to date is the **only** hard floor. `recommended_final_cost` and
`worst_credible_final_cost` are NEVER capped at ERP projected cost, revised budget, committed cost,
owner SOV value, Procore pay-app value, or prior model output. Those are reported as references and
never used to clamp. ERP projected cost is never a fallback floor and is never presented as a modeled
answer — evidence-poor codes resolve to `insufficient_evidence` (recommended = actuals), not ERP.

Overrun is defined against **current projected cost** (`overrun_projected =
overrun_vs_current_projected_cost`); separate flags also test revised budget, committed cost, and
owner SOV value.

## Module map (build order)

| Module | Responsibility |
|---|---|
| `db_inventory.py` | Read-only (`mode=ro`) DB schema+counts inventory; project-level change-order $ aggregation (never attributed to codes). |
| `trend.py` | Recent vs prior burn, acceleration/deceleration, volatility, recency, late-cost emergence, credits/deductive, `trend_signal`. |
| `schedule_association.py` | Classify each code: direct / cost_code_family / vendor_or_commitment / owner_scope / division / project_level / none. `direct` requires a deterministic unique mapped activity link. `project_level` is context only (weight 0.0). |
| `estimators_uncapped.py` | 6 uncapped estimators (owner/procore progress, schedule remaining-work, trend projection, commitment exposure, cpi blend) + 2 ERP references. ETC (future cost) and EAC (= actual + ETC) are distinct fields. Floored only to actuals. |
| `evidence.py` | Wraps `forecast_accuracy.signals.build_signal_bundle`; merges ERP/owner/procore extras + trend + association. |
| `reconcile_final.py` | Dual posture: balanced-central `recommended_final_cost` + evidence-supported `worst_credible_final_cost`. Overrun flags, `forecast_direction`, `overrun_basis`, primary evidence, data gaps. |
| `overrun_register.py` | One row per overrun code, severity-tiered, ranked by amount. |
| `confidence_intel.py` | 0-1 confidence extending `forecast_accuracy.confidence` with a schedule-association-strength component. |
| `change_explanation.py` | Recommended final cost vs prior package model number and crosswalk-v2 rule-based number. |
| `backtest_strong.py` | Multi as-of-T (40/60/80%) reconstruction on the owner≥95% cohort; per-method MAPE/bias; division/family cohort breakdowns; before/after vs the prior package; excluded rows. |
| `generate_forecast_intelligence_package.py` | Orchestrator: discovery, per-127 build, register/summary/audit, validation gates, safety scan, manifest, determinism, advisory LLM reuse. |

The local-Ollama layer is **reused verbatim** from `forecast_accuracy.llm` (advisory, never numeric,
safety-scanned, template fallback, excluded from the determinism gate).

## Estimator → final-cost flow

1. Each code's evidence bundle feeds the 6 uncapped estimators (ERP entries are references only).
2. `reconcile_final` weights applicable independent estimates by `reliability × calibration ×
   association_scale` (schedule estimate scaled by `schedule_confidence`).
3. `recommended_final_cost` = max(actuals, weighted-central); when trend supports overrun or any
   estimate exceeds ERP, it is biased toward the p75 so a credible overrun is not averaged away.
4. `worst_credible_final_cost` = max(actuals, p90, commitment-exposure floor).
5. Decrease is emitted only when defensible (near-complete + stable burn + no commitment overrun);
   otherwise a sub-projected estimate downgrades to `hold`.

## Schedule association ladder

`direct` 1.0 → `cost_code_family` 0.6 → `vendor_or_commitment` 0.5 → `owner_scope` 0.4 →
`division` 0.3 → `project_level` 0.0 (context only) → `none` 0.0. Family/owner/division borrow a
revised-budget-prorated share of the group's remaining schedule duration, heavily down-weighted by
confidence. `vendor_or_commitment` is structurally supported but unavailable in current Tropical data
(empty per-code vendor/commitment links), so it resolves to weaker tiers — never invented.

## Determinism & safety

The quantitative core is byte-deterministic under a frozen stamp (two runs diff identical except
`llm/`). The DB inventory is schema+counts only (no payloads, no timestamps), so it does not perturb
determinism. Safety scan (emails/phones/tokens/keys/signed URLs/private blobs/PEM/raw-payload keys)
runs over every emitted artifact and must report zero fail-category findings.

## Validation gates

`output_files_parse`, `one_row_per_canonical_key` (127), `canonical_only_codes`,
`final_cost_geq_actuals`, `every_estimate_geq_actuals`, `forecast_is_uncapped` (recommendations
exceed references AND estimators produce values above ERP/budget), `overrun_not_suppressed` (no
material recommended>projected with `overrun_projected=false`), `direct_assoc_requires_deterministic_link`,
`no_payapp_overwrite_of_actuals`, `db_inventory_no_payloads`, `backtest_cohort_present`,
`safety_scan_passed`.

## Guardrails

Code only under this subproject; output only a new timestamped package under the data root. No
source/Excel/SQLite/external mutation (DB opened read-only). Decimal-only money. Every recommendation
`requires_human_acceptance`. Accounting actuals are truth and are never overwritten by pay-app values.
