# Forecast History-Informed (historical-forecast-assumption evidence)

Status: current. Module: `src/construction_financial_review/forecast_history_informed/`.
CLI: `forecast-history-informed`. Output: `forecast_history_informed_package_tropical_<stamp>/`.

## Why this exists

The accepted forecast stack (context → analysis → intelligence → monthly → probability) never uses the
**prior forecast assumptions** captured in the two extracted historical workbooks (cash-flow and GC/GR
forecast history, Feb 2025 → Apr 2026). This slice is an additive **evidence layer**: it mines those
prior forecasts, validates each against CostEntries/Sage actual cost, and surfaces ADVISORY
recommendations, confidence/uncertainty shifts, monthly-shape signals and probability-spread
suggestions. It never replaces or mutates an accepted package.

**Posture (non-negotiable).** Historical forecast is prior-assumption evidence — *never actual cost,
never a hard cap.* CostEntries/Sage incurred cost is the primary reality check. Actual cost to date is
the only hard floor; nothing is capped above ERP/budget/commitment/owner SOV/pay-app/prior forecast.
The local LLM is advisory only (no numeric output) and excluded from the determinism gate. Every row
requires human acceptance; no accepted intelligence/monthly/probability package is changed.

## Inputs (read-only)

- **Historical** (fixed-name dirs from config): `cash_flow_forecast_history_json_package/` (132 cost
  codes; `period_type` ∈ {actual, forecast, mixed_actual_forecast_range}) and
  `gcgr_forecast_history_json_package/` (37 codes; `amount_type` ∈ {actual, forecast, original,
  projected, variance}). Both are normalized into one monthly-value record.
- **Context** pkg: `canonical/budget_codes.jsonl` (127 — the SOLE mapping authority),
  `summaries/budget_code_forecast_context.jsonl` (per-code actuals truth + budget amounts).
- **Intelligence / Monthly / Probability** packages (latest by glob): recommendations, trend, schedule
  and confidence evidence; monthly basis + source shares; sigma + overrun probability. Read-only.

## Method (deterministic)

1. **Normalize** both historical shapes into a unified record (`history_io`); reconcile loaded counts to
   each package's manifest/validation report; capture pre-run source hashes.
2. **Map** each bare historical `cost_code` to canonical keys via `schedule_mapping.build_canonical_index`
   (`history_mapping`): unique match, multi-category **rollup** (never force a category), family rollup,
   or explicit **unmapped**. Duplicate same-sheet codes keep source-row + description lineage; 10-XX
   General-Requirements codes are flagged description-sensitive.
3. **Signal** (`history_signals`): per snapshot, remaining forecast = Σ forecast-classified future
   amounts. The across-snapshot series yields slope, persistence, zero-persistence, stability/volatility
   scores and a **pattern class** (inactive / stable-zero / stable-nonzero / increasing / decreasing-
   tapering / volatile); the latest snapshot's monthly curve yields a **curve-shape class** (flat /
   linear / front- or back-loaded / s-curve / tapering-closeout / spike / volatile).
4. **Validate vs actuals** (`history_actual_validation`): compare the latest prior remaining forecast to
   CostEntries actual cost in the post-snapshot window — variance, inactivity, recent 1/3/6/12-mo burn,
   escalation, credits/reversals — and classify (validated_zero_inactive / validated_aligned /
   contradicted_escalation / contradicted_unexpected_actuals / history_overstated / inconclusive). A
   recent escalating trend produces an **override score** so stale history never wins.
5. **Reliability** (`history_reliability`): blend persistence/recency/stability/actual-validation/
   contradiction/schedule/invoice support → overall score + band; **contradiction collapses the score**.
6. **Advisory outputs** (`history_recommendations` / `history_monthly_distribution` /
   `history_probability_adjustments`): a forecast adjustment nudged toward the historical-implied EAC
   *in proportion to reliability* (floored at actuals, never capped, `do_not_auto_apply`); curve-shape
   monthly-weight suggestions; sigma-multiplier / tail-shift suggestions (tighten when validated, widen
   when contradicted). None of these edit an accepted package.
7. **GC-fee proportionality** (`gcgr_proportionality`): tests the 20-18-110 "CONTRACTORS FEE" taper
   hypothesis against collective 15-* cost-of-work percent-complete. Reports `confirmed` **only** when
   the fee's remaining genuinely declines as 15-* completes AND the implied fee total is stable;
   otherwise `tapering_consistent_not_confirmed` / `unsupported` / `insufficient_evidence`.

## Module map

| Module | Responsibility |
|---|---|
| `history_io.py` | Discover + load all inputs (read-only); normalize both historical shapes; count reconciliation; pre-run source hashes. |
| `history_mapping.py` | cost_code → canonical (unique / multi-category rollup / family / unmapped); duplicate-code + 10-XX + watch-code presence. |
| `history_signals.py` | Remaining-forecast series, slope, persistence/stability/volatility scores, pattern class, monthly curve + curve-shape classifier. |
| `history_actual_validation.py` | Prior forecast vs CostEntries actuals: variance, inactivity, burn, escalation/credits, override score, validation class. |
| `history_reliability.py` | Reliability blend + band + reason codes (contradiction collapses it). |
| `history_recommendations.py` | Advisory forecast adjustment (reliability-weighted, floored, uncapped, do-not-auto-apply). |
| `history_monthly_distribution.py` | Advisory curve-shape monthly-weight suggestions. |
| `history_probability_adjustments.py` | Advisory sigma-multiplier / tail-shift suggestions. |
| `gcgr_proportionality.py` | GC-fee taper / 15-* proportionality hypothesis test + audit. |
| `validation.py` | Fail-closed gates. |
| `generate_forecast_history_informed_package.py` | Orchestrator: collections, determinism self-check, advisory LLM, audit/meta/README/SCHEMA, safety, manifest. |

Reuses `common/*` (io, money, safety, validation, hashing, budget_keys),
`schedule_analysis.schedule_mapping.build_canonical_index`, `schedule_analysis.schedule_io`,
`forecast_intelligence.db_inventory`, and `forecast_accuracy.llm` (advisory only).

## Determinism & validation

Quantitative core (the 14 data files + the four analytic audit files) is byte-identical across two runs
with the same `--frozen-stamp`; the orchestrator self-checks this and the e2e test byte-diffs the
package (excluding `llm/`, the run-metadata files, and environmental audit files which carry generated
paths/timestamps/DB-schema-counts). Fail-closed gates include: output parse; meta/docs present;
historical source lineage; count reconciliation; canonical mapping audit; canonical-only-or-explicit-
unmapped; duplicate-code warnings; CostEntries actuals primary truth; **no historical forecast as
actual**; **no prior forecast hard cap**; actuals floor preserved; zero recommendations require
inactivity; escalating actuals override stale history; history-vs-actual divergence reported; GC-fee
proportionality audit present; determinism; safety scan; **source hashes unchanged** (no-mutation
proof); no SQLite mutation; **no live external calls (localhost Ollama only under `--with-llm`)**.

## Config (`config/projects/tropical.json` → `forecast_history_informed`)

`cash_flow_history_package` / `gcgr_history_package` (fixed dir names); intelligence/monthly/probability
globs; `minimum_zero_persistence_snapshots` (3); `actual_inactivity_months_for_zero_support` (12);
`history_recency_half_life_months` (6); `history_max_weight_when_unvalidated` (0.20) /
`history_max_weight_when_validated` (0.45). Every default is documented here.

## Notable findings (2026-June data)

- `20-18-110` "CONTRACTORS FEE" (→ `1000.20-18-110.OVH`) declines 854k→315k while 15-* completion rises
  0.58→0.86; implied fee total stable at ~$2.05M (cov 0.05) → proportionality **confirmed**.
- `03-01-025` (→ `0000.03-01-025.MAT`, GC/GR only) is stable-zero/inactive → zero-remaining candidate
  with actual-inactivity support.
- `15-16-100` is **absent** from cash-flow + GC/GR history, canonical BudgetDetails, and all current
  packages (verified) → reported explicitly, not analyzed.

## How a later consuming slice could use this

A future, separately-directed slice could ingest the advisory `history_informed_*` rows (all
`do_not_auto_apply`) as one more evidence family into intelligence/monthly/probability — but only under
explicit human acceptance; this slice deliberately stops at surfacing evidence.
