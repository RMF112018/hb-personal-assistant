# Time-series shadow estimator — live evidence (20260621T183650Z)

Go/no-go evidence for PR 3 (promoting `timeseries_eac` into the weighted ensemble). Produced by
`forecast-intelligence` on the real tropical data root under a frozen stamp (deterministic). The
shadow estimator is emitted and backtested but **never weighted** — the central forecast is unchanged
(ADR 286).

## Backtest result — engine does NOT yet beat naive (do not promote)

Backend: `classical_ensemble_v1` (numpy naive/drift/Holt/theta-like median; statsforecast deferred —
not 3.14-installable). Holdout: last h completed months (h=1/2/3 by length), fit on the prefix,
predict h, vs a naive baseline.

| Metric | Engine | Naive |
|--------|--------|-------|
| Eligible codes | 79 | 79 |
| Median abs % error | **0.5514** | **0.5042** |
| Engine ≥ naive (win-or-tie) | **39 / 79 (49.4%)** | — |

The classical ensemble is **not** more accurate than a naive last-month baseline on tropical's short,
noisy monthly burn (both ~50% MAPE — single/few-month construction burn is inherently hard to predict
from history alone). **Recommendation: do NOT promote to `INDEPENDENT_METHODS` yet.** Next options,
re-evaluated through this same shadow harness with zero forecast risk:
- a stronger backend (real statsforecast AutoARIMA/AutoETS once 3.14-compatible);
- per-code model selection / longer fit windows;
- blending the time-series signal only where it beats naive.

## Files
- `statsforecast_shadow_backtest.json` — holdout accuracy (engine vs naive), per code + aggregate.
- `statsforecast_shadow_comparison.jsonl` — per-code `timeseries_eac` vs the central recommended final cost (85 rows).
