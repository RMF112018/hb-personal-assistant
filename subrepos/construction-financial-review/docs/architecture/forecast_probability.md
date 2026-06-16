# Forecast Probability (probabilistic validation of the cost estimate)

Status: current. Module: `src/construction_financial_review/forecast_probability/`.
CLI: `forecast-probability`. Output: `forecast_probability_package_tropical_<stamp>/`.

## Why this exists

The accepted `forecast_intelligence` slice produces a single deterministic anticipated final cost
(recommended + worst-credible) per budget code, and `forecast_monthly` time-phases it. Neither answers
*how likely*. This slice is a probabilistic **validation layer** (not a replacement) that stress-tests
those accepted outputs with a Monte Carlo simulation and quantifies the probability, range and timing of
outcomes:

- P10 / P50 / P80 / P90 / P95 final cost — project and per budget code.
- Probability the recommended final cost is met / exceeded.
- Per-code probability of exceeding current projected cost and revised budget.
- **Project-level** probability of exceeding the revised budget total, with expected and
  P80/P90/P95 overrun vs revised budget (mirrors the current-projected-total metrics).
- Which budget codes drive downside exposure (contribution to the project P90 tail).
- Which months carry the greatest cost and overrun risk.
- Simulated project risk vs the deterministic recommended (P50 anchor) and worst-credible values.
- Which assumptions are most sensitive (one-at-a-time ΔP90); risk contribution by division and owner
  SOV scope.

## Dependencies

This is the first slice that uses third-party libraries: **numpy** (vectorized Monte Carlo) and
**scipy** (`scipy.stats` for distribution calibration, Spearman, quantile sampling). They are declared
in `pyproject.toml`. Every other slice and the deterministic forecast core remain stdlib-only. Money is
serialized as Decimal strings at the JSON boundary; simulation internals are float64.

## Core principle

Actual cost to date is the ONLY hard lower bound: every simulated final cost is floored at actuals and
is **never capped** at ERP projected cost, revised budget, committed cost, owner SOV value, Procore
pay-app value, or any prior model output — the upside is uncapped. The local LLM may produce advisory
text only; it never produces a numeric simulation result. The quantitative core is deterministic
(`--seed` + frozen stamp ⇒ byte-identical). Subcontractor invoice and owner pay-app values remain
evidence only, never actuals.

## Statistical method

**Per code — shifted lognormal on cost-to-complete (CTC):** `final = actual + CTC`,
`CTC = exp(mu + sigma·Z)`, `Z ~ N(0,1)`. This makes the actuals floor exact and the upside unbounded.

- `mu = ln(recommended_cost_to_complete)` ⇒ the lognormal median equals the deterministic recommended
  CTC, so **the deterministic recommended final cost is the per-code P50 by construction** (independent
  of sigma).
- `sigma_worst` solves `median·exp(sigma·z_q) = worst_credible_cost_to_complete`, so the deterministic
  worst-credible lands near its high quantile (default P90).
- Spread is widened by evidence the deterministic package already computed:
  `sigma_evidence = (w_cov·σ_cov + w_mape·σ_mape + w_div·σ_div)·(1 + k·(1 − confidence_score))`, where
  `σ_cov = sqrt(ln(1 + cov²))` (exact lognormal CoV identity), `σ_mape = ln(1 + MAPE)` (effective-weight
  MAPE from the backtest), `σ_div` = model divergence. `sigma = clamp(max(sigma_worst, sigma_evidence),
  floor, cap)`. Weights are MAPE/worst-credible-led (the final-cost signals) with volatility secondary.
- `overrun_existence_confidence` fattens the right tail by lowering the quantile that worst-credible is
  mapped to — **the median (P50 anchor) is preserved exactly.**
- Codes with CTC ≤ \$0.01 are treated as near-complete: `final = actual`, zero spread.

**Correlation — one-factor Gaussian copula.** Codes do not overrun independently (shared escalation,
labor market, GC-wide slip). Each run draws one shared systemic factor `M ~ N(0,1)`; per code
`Z = sqrt(ρ)·M + sqrt(1−ρ)·ε`, giving pairwise correlation `ρ` (config, default 0.35). This widens the
project tail correctly; independence would understate it via false diversification.

**Engine.** Vectorized numpy `default_rng(seed)` (PCG64), `runs × codes` matrices, antithetic variates
for variance reduction (Latin-Hypercube on the systemic factor optionally, config). Monthly costs phase
each run's CTC by a Dirichlet perturbation of the deterministic monthly weights (concentration scales
with `monthly_distribution_confidence`), so per run `Σ months == CTC` exactly.

**Later `--forecast-start-month` (carry-forward, not reallocation).** When the requested start month is
after the monthly package window start, the prior-month deterministic CTC is *carried forward*, not
re-phased into the shortened window. Per code the monthly package's `recommended_month_cost` /
`worst_credible_month_cost` for months `< start` are summed; `calibrate_code` subtracts them so the
lognormal models only the remaining-window CTC (`window_recommended_ctc = max(0, full − prior)`), and the
subtracted recommended amount is added back in the engine as a fixed deterministic addend
(`final = accounting_actual + carried_prior_forecast + window_CTC`). The accounting actual stays the only
hard floor; carried forecast is **never** treated as actual cost. Default runs (no override) carry zero
and are byte-identical to before. `project_summary.window_reconciliation` reports the four-way split
(`accounting_actual_cost_to_date`, `deterministic_prior_forecast_before_probability_window`,
`simulated_probability_window_cost_to_complete`, `simulated_final_cost_including_carried_forecast`).

## Module map

| Module | Responsibility |
|---|---|
| `distributions.py` | Per-code lognormal-CTC calibration (median anchor, worst-credible quantile, evidence-blended sigma, overrun-tail shift); config parameter resolution. |
| `simulation_inputs.py` | Load the accepted anchor + monthly packages and (for the PIT backtest) the context package owner-history + actuals (all read-only); effective-weight MAPE; build per-code specs and stacked numpy arrays. Sums prior-month CTC for a later `--forecast-start-month`; loads the authoritative owner SOV scope crosswalk assignment (budget code → owner scope). |
| `simulate.py` | Vectorized Monte Carlo: one-factor copula → lognormal final costs (floored, uncapped) + Dirichlet monthly phasing; adds the deterministic carried prior-month forecast addend (zero on the default path). |
| `risk_metrics.py` | Percentiles, exceedance probabilities, VaR/CVaR, co-tail downside contribution, monthly risk, percentile-rank of the deterministic anchors. |
| `sensitivity.py` | One-at-a-time ΔP90 by spread source (authoritative), Spearman code drivers, systemic-vs-idiosyncratic variance share. |
| `probabilistic_backtest.py` | PIT + coverage calibration: reconstruct the near-complete cohort via `forecast_intelligence.backtest_strong`, rebuild the predictive shifted-lognormal-on-CTC at each as-of point (40/60/80%), and test realized finals (coverage at P10-P90 / P05-P95, PIT-uniformity KS). Dispersion-adequacy vs historical MAPE kept as a secondary view; honest about the small cohort. |
| `generate_probabilistic_validation_package.py` | Orchestrator: package, determinism self-check, validation gates, safety, manifest, advisory LLM. |

Reuses `common/*`, `forecast_intelligence.db_inventory`, `forecast_intelligence.backtest_strong`
(deterministic cohort reconstruction for the PIT test), `forecast_accuracy.signals` +
`schedule_analysis.schedule_io` (read-only context-package loaders), and `forecast_accuracy.llm`.

## Hardening

- **Determinism block** in `validation_report.json` (`performed`, `quantitative_core_byte_identical`,
  `llm_excluded_from_byte_diff`, `frozen_stamp`, `seed`, `runs`, `diff_result`, per-file hashes) + gate
  `determinism_passed`. The orchestrator rebuilds the quant core twice into temp dirs and byte-diffs.
- **LLM receipts** carry `numeric_outputs_from_llm: false` plus the standard model/backend/status/hash
  fields; the narrative schema has no numeric keys. LLM is advisory only and excluded from the diff.
- **No-upper-cap audit** (`audit/no_upper_cap_audit.json`): one record per code — distribution family,
  `actual_floor_applied`, `upper_cap_applied` (false), `upper_cap_source` (null),
  `reference_values_reported_only`, P95-vs-(current-projected / revised-budget / worst-credible),
  `validation_status`. Gates assert no non-near code is capped and no cap source is a reference value.

## Compatibility outputs (additive aliases; canonical files preserved)

First-class outputs — emitted, parseable, listed in the manifest, documented in SCHEMA.md, validated, and
in the deterministic byte-diff. `simulation_results_project.json`,
`simulation_results_by_budget_code.jsonl`, `simulation_results_by_month.jsonl` (project-month) mirror
their canonical counterparts. `probabilistic_overrun_risk_register.jsonl` is a **material** subset:
included iff `P(exceeds current projected) ≥ 0.20` AND (expected overrun ≥ \$25,000 OR ≥ 5% of current
projected), each row carrying its `materiality_threshold_basis`. `budget_code_sensitivity.jsonl`
(per-code downside contribution + Spearman driver), `division_sensitivity.jsonl`, and
`owner_scope_sensitivity.jsonl` aggregate risk contribution; owner scope uses the authoritative owner SOV
scope crosswalk and falls back to a single explicit unavailable row only when no assignment resolves.

## Validation gates (fail-closed)

output_files_parse; per-code completeness (127); canonical-only codes; percentile monotonicity (code +
project); final-cost floor at actuals; no-upper-cap (≥1 code P95 beyond its worst-credible AND project
P95 beyond deterministic recommended); **no-upper-cap audit present**; **no code upper-capped**; **no cap
source is a reference value**; **revised-budget probability present and in [0,1]**; **compatibility alias
files present and parseable**; **`--forecast-start-month` no full-CTC reallocation**; P50 aligns with
deterministic recommended (≥90% of non-complete codes within tolerance AND recommended total a central
project percentile); monthly reconciles to simulated CTC; probability fields in [0,1]; sensitivity ranking
present; backtest cohort reported; `determinism_passed`; LLM no numeric outputs + receipt fields when
used; db_inventory no payloads; safety scan.

## Guardrails

Additive and contained under `forecast_probability/` (plus CLI wiring, deps, config, docs). Output only
a new timestamped package under the data root. No source/Excel/SQLite/external mutation (DB read-only).
Decimal money; actuals the only hard floor; nothing capped above any reference; every per-code row
`requires_human_acceptance`. Probabilistic numbers are advisory and require human acceptance.
