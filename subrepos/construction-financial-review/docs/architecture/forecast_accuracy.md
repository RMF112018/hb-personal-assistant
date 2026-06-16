# Architecture — Forecast Accuracy, Ability & Confidence Slice

## Purpose

Improve forecasting accuracy, ability, and confidence with independent quantitative models +
backtest calibration + an advisory local-Ollama reasoning layer, without overriding accounting
actuals or the authoritative rule-based recommendation.

## Module layout `src/construction_financial_review/forecast_accuracy/`

| Module | Responsibility |
|--------|----------------|
| `signals.py` | Per-budget-code signal bundle (actuals/monthly series, budget amounts, owner, procore, commitments, schedule, two horizons, burn + volatility, evidence depth). Loaders for owner per-application history and schedule cash-flow totals. |
| `estimators.py` | Five independent EAC/ETC models + two ERP baselines; each floored to actuals with an applicability gate (incl. near-complete burn gate). |
| `reconcile.py` | Reliability x calibration weighted ensemble → `model_reconciled_eac`, advisory `model_recommended_projected_cost`, range, divergence, contributions. |
| `backtest.py` | As-of reconstruction on the owner-≥95% cohort → per-method MAPE/bias + calibration multipliers. |
| `confidence.py` | Calibrated 0–1 confidence (density, agreement, recency, stability) + drivers + band. |
| `forecast_adequacy.py` | ERP-vs-model classification (materiality-gated) + severity. |
| `llm/client.py` | Stdlib-`urllib` Ollama client (`/api/tags`, `/api/generate`, temp 0 + seed, redacted errors). |
| `llm/backend.py` | Backend protocol + `StaticBackend` mock. |
| `llm/narrate.py` | Facts-only prompts, JSON validation, safety-scan fail-closed, hash receipts, deterministic template fallback. |
| `generate_forecast_accuracy_package.py` | Orchestrator: signals → estimate → reconcile → backtest/calibrate → confidence → adequacy → (live/mock) narrate → write + manifest + validation + safety + git metadata. |

Reuses `common/` (money/dates/budget_keys/io/hashing/safety/validation) and `schedule_analysis`
(`discover_packages`, schedule manifest reader). No third-party deps.

## Data flow

```
context (actuals, budget, owner, commitments) ─┐
crosswalk_v2 recommendation (authoritative) ────┼─► signals ─► estimators ─► reconcile ─► model_recommended (advisory)
schedule_integrated rollup + cashflow ──────────┘                 │              │
owner per-app history ─► backtest ─► calibration weights ─────────┘              ├─► confidence (0-1)
                                                                                  ├─► adequacy (ERP vs model)
                                                                                  └─► llm narratives (advisory, subset)
```

## Invariants

- Every EAC ≥ actual-to-date; the advisory model number is floored to actuals and never overwrites
  the authoritative rule-based `recommended_projected_cost` (validation-gated).
- Quantitative core is byte-deterministic across `--frozen-stamp` runs; `llm/` outputs are advisory,
  safety-scanned fail-closed, hash-receipted, and excluded from the determinism gate.
- Backtest calibration is honest: it transparently down-weights methods that backtest poorly
  (e.g. naive burn-rate) and up-weights accurate ones (commitment/owner/cpi).

## Integration point

CLI `forecast-accuracy` (import-dispatched, config-driven) with `--with-llm`; project-config `llm`
block (model, fallback, endpoint, temperature, seed, timeout).
