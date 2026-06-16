# Tropical 2026-June — approved decisions & deferred work

Project: Tropical World Nursery Senior Living Facility · `tropical` · `23-435-01` · `2026-June`.
Approved by Bobby Fetting on 2026-06-14.

## Canonical interpretation rules
- BudgetDetails is the master budget-code universe (127 keys); keys are never invented.
- CostEntries are accounting actual-cost truth.
- Owner pay apps are owner-recognized billing/progress evidence.
- Procore subcontractor pay apps are vendor/commitment progress evidence.
- The authoritative crosswalk governs owner/procore scope relationships.
- No fuzzy matching; no pay-app value replaces actual cost.

## Approved analysis decisions
- `budget_amount = budget_amounts.revised_budget`; `current_projected_cost = budget_amounts.projected_costs`
  (projected_budget / estimated_cost_at_completion preserved as reference only).
- Materiality gate: `|gap| ≥ $25,000` **AND** `≥ 10%` of the larger basis. Severity tiers: critical
  (≥$250k or ≥25%), high (≥$100k or ≥15%), medium (passes gate), low.
- **Floor-to-actuals increase:** when actuals exceed projected cost,
  `recommended_projected_cost = actual_cost_all_source_to_date`,
  `recommended_forecast_adjustment = actual − projected`. Absolute precedence — review flags may lower
  confidence but never suppress the floor.
- **Decrease** only when fully gated (owner substantially complete, immaterial balance-to-finish, no
  remaining Procore exposure, material proj>actual, no June/mapping/credit issues); else review_required.
- **Actuals-only holds are `medium`** unless no-exposure is proven (forecast_to_complete 0 + immaterial
  remaining + no positive Procore remaining).
- **Owner/procore comparisons use the owner-scope rollup** with sell-value-vs-cost caution. For
  one-to-many owner SOV scopes, compare only at the rollup; do **not** allocate owner summary dollars to
  child budget codes (no allocation schedule). Children inherit rollup context only.
- `10-XX-XXX` is **description-sensitive**: GENERAL REQUIREMENTS → GR row, all other 10-XX-XXX rows →
  non-GR row. Routing must be unambiguous.
- The final authoritative crosswalk covers **all 127** canonical BudgetDetails codes and **42/42**
  Procore latest WBS codes; 0 unresolved, 0 duplicate.

## Source-of-truth note (refinement #1)
The four generators were consolidated from the **validated package-internal copies** (not from
`/tmp`); their SHA-256 hashes are recorded in `examples/tropical/input_inventory.example.json` and were
confirmed byte-identical to the working copies.

## Schedule integration decisions (Stage 6)
Schedule data is **timing / remaining-work / sequencing / risk** evidence only. It never becomes
accounting actual cost, never earns value, and never by itself sets `recommended_projected_cost`,
creates a numeric increase, or creates a decrease. Baseline = crosswalk_v2 recommendations.
- **Forecast exhaustion (`actuals_near_projected`)** is deterministic:
  `actual_cost_all_source_to_date >= 0.90 * current_projected_cost`.
- **Material remaining work** = `>= 3` open activities **OR** `>= 14` remaining 8h-days.
- **Zero vs negative float are separated.** `total_float <= 0` is a critical/longest-path **proxy
  only** (the source has no explicit longest-path flag). Risk **escalation** uses **negative** float
  (`< 0`) on **open** work — never zero float alone.
- **Mapping authority is canonical BudgetDetails only.** A schedule cost code that resolves to exactly
  one canonical key is `mapped`; one spanning multiple categories (e.g. `15-16-110` → `.MAT`/`.SUB`) is
  `ambiguous` (no forced key). The extractor's `candidate_budget_code_keys` are **supporting evidence
  only** and cannot create a `mapped` key.
- **Decrease guardrail:** a `decrease_forecast` with material remaining schedule work is downgraded to
  `review_required` with the number cleared (`schedule_blocks_decrease`).
- **Cash-flow timing** is duration-weighted across months, **confidence capped at `medium`** (no
  validated cost/resource loading); ambiguous/unmapped exposure stays `not_allocated`; monthly amounts
  always tie to remaining exposure within rounding tolerance.

## Forecast accuracy decisions (Stage 7)
Independent quantitative models cross-check the ERP forecast; accounting actuals remain truth and are
never overridden. Every EAC is floored to actual-to-date.
- **Advisory model number.** An explicit `model_recommended_projected_cost` (floored to actuals,
  `requires_human_acceptance: true`) is emitted ALONGSIDE — never replacing — the authoritative
  rule-based `recommended_projected_cost`.
- **Five independent EAC methods** (burn-rate, owner %-complete, commitment floor, schedule ETC, CPI
  proxy) plus two ERP baselines (comparison only). Burn-rate is **gated off near-complete codes**
  (owner ≥95% or schedule complete) to avoid extrapolating finished scope.
- **Backtest calibration.** On the owner-≥95% completed cohort, each method's EAC is recomputed at a
  mid-progress as-of period and scored vs realized; calibration multiplier = `(1/(1+MAPE))` normalized
  to mean 1.0. The ensemble down-weights poorly-backtesting methods (TWN: burn-rate) and up-weights
  accurate ones (commitment/owner/cpi).
- **Calibrated confidence** is a 0–1 score (signal density, model agreement, recency, burn stability),
  reported alongside a band and drivers.
- **Forecast adequacy** compares ERP vs model with the $25k AND 10% gate → likely_low / adequate /
  likely_high / indeterminate.
- **Local-Ollama advisory layer** (`--with-llm`, default `qwen2.5:14b`, temp 0 + fixed seed) explains
  the deterministic numbers for a review subset. Advisory only: prompts carry numeric facts only,
  outputs are JSON-validated, **safety-scanned fail-closed to a deterministic template**, hash-
  receipted, and never produce a number. The quantitative core is byte-deterministic; the `llm/`
  outputs are excluded from the determinism gate.

## Deferred work
- **Parameterize the generators.** They currently carry hardcoded Tropical / 2026-June data-root and
  package-name paths. Until parameterized, the CLI `run-*` commands are Tropical-only and fail clearly
  for other projects. (The schedule-integrated and forecast-accuracy generators are config-driven.)
- Extract the generators' inline helpers to import the shared `common/` library (currently the
  generators remain self-contained; `common/` is the tested library surface).
- Optional packaging install (`pip install -e ".[dev]"`); validation here runs without install via
  `PYTHONPATH=src`.
- Apply the analysis-package refinements (#2–#5 from the v2 session) to a v1 patch if a standalone v1
  refresh is ever needed (already incorporated in crosswalk v2).
