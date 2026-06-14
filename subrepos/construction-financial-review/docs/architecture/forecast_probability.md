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
- Which budget codes drive downside exposure (contribution to the project P90 tail).
- Which months carry the greatest cost and overrun risk.
- Simulated project risk vs the deterministic recommended (P50 anchor) and worst-credible values.
- Which assumptions are most sensitive (one-at-a-time ΔP90).

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

## Module map

| Module | Responsibility |
|---|---|
| `distributions.py` | Per-code lognormal-CTC calibration (median anchor, worst-credible quantile, evidence-blended sigma, overrun-tail shift); config parameter resolution. |
| `simulation_inputs.py` | Load the accepted anchor + monthly packages (read-only); effective-weight MAPE; build per-code specs and stacked numpy arrays. |
| `simulate.py` | Vectorized Monte Carlo: one-factor copula → lognormal final costs (floored, uncapped) + Dirichlet monthly phasing. |
| `risk_metrics.py` | Percentiles, exceedance probabilities, VaR/CVaR, co-tail downside contribution, monthly risk, percentile-rank of the deterministic anchors. |
| `sensitivity.py` | One-at-a-time ΔP90 by spread source (authoritative), Spearman code drivers, systemic-vs-idiosyncratic variance share. |
| `probabilistic_backtest.py` | Dispersion-adequacy vs historical method MAPE on the near-complete cohort; honest about the small cohort and absent row-level PIT. |
| `generate_probabilistic_validation_package.py` | Orchestrator: package, determinism self-check, validation gates, safety, manifest, advisory LLM. |

Reuses `common/*`, `forecast_intelligence.db_inventory`, and `forecast_accuracy.llm`.

## Hardening

- **Determinism block** in `validation_report.json` (`performed`, `quantitative_core_byte_identical`,
  `llm_excluded_from_byte_diff`, `frozen_stamp`, `seed`, `runs`, `diff_result`, per-file hashes) + gate
  `determinism_passed`. The orchestrator rebuilds the quant core twice into temp dirs and byte-diffs.
- **LLM receipts** carry `numeric_outputs_from_llm: false` plus the standard model/backend/status/hash
  fields; the narrative schema has no numeric keys. LLM is advisory only and excluded from the diff.

## Validation gates (fail-closed)

output_files_parse; per-code completeness (127); canonical-only codes; percentile monotonicity (code +
project); final-cost floor at actuals; no-upper-cap (≥1 code P95 beyond its worst-credible AND project
P95 beyond deterministic recommended); P50 aligns with deterministic recommended (≥90% of non-complete
codes within tolerance AND recommended total a central project percentile); monthly reconciles to
simulated CTC; probability fields in [0,1]; sensitivity ranking present; backtest cohort reported;
`determinism_passed`; LLM no numeric outputs + receipt fields when used; db_inventory no payloads; safety
scan.

## Guardrails

Additive and contained under `forecast_probability/` (plus CLI wiring, deps, config, docs). Output only
a new timestamped package under the data root. No source/Excel/SQLite/external mutation (DB read-only).
Decimal money; actuals the only hard floor; nothing capped above any reference; every per-code row
`requires_human_acceptance`. Probabilistic numbers are advisory and require human acceptance.
