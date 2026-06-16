# Stage 7 — Forecast Accuracy, Ability & Confidence

Adds independent quantitative forecasting on top of the crosswalk-v2 recommendation: multiple EAC/ETC
models, a reconciled advisory forecast, backtest-calibrated confidence, ERP adequacy flags, and an
optional advisory local-Ollama narrative layer. Accounting actuals (CostEntries) remain truth.

## Inputs (discovered from config + data root)

- Forecast context package — canonical 127 budget codes, `monthly_actuals`, all `budget_amounts.*`,
  owner pay-app (latest + per-application history), procore, commitments.
- Crosswalk-v2 analysis package — authoritative rule-based `forecast_recommendations_by_budget_code.jsonl`
  (read-only; never modified).
- Schedule-integrated package — `schedule_budget_code_rollup.jsonl` + cash-flow curve (remaining work,
  remaining duration/finish).
- Schedule raw package — data date + scheduled finish (forecast horizons).

## Independent EAC/ETC models (each floored to actual-to-date)

| Method | Basis | Applicability |
|--------|-------|---------------|
| `burn_rate` | actual + avg monthly burn x project remaining months | >=3 burn months; **gated off near-complete** (owner >=95% / schedule complete) |
| `owner_percent_complete` | actual / owner % complete | owner mapped, % in [0.05, 1] |
| `commitment_floor` | max(committed, erp-to-date, actual) | committed_costs > 0 |
| `schedule_etc` | actual + burn x remaining schedule duration | schedule mapped + open work |
| `cpi_proxy` | actual / blended completion % (owner/cost/schedule) | revised_budget > 0 |
| `baseline_projected`, `baseline_erp_eac` | ERP workbook (comparison only, `source=erp`) | present |

## Reconciliation, confidence, adequacy

- **Reconcile:** reliability x backtest-calibration weighted point → `model_reconciled_eac` and the
  advisory `model_recommended_projected_cost` (floored to actuals, `requires_human_acceptance: true`),
  plus low/high range and a normalized **divergence** metric. ERP baselines do not drive the number.
- **Backtest:** on the owner-≥95% completed cohort, recompute each method's EAC at a mid-progress as-of
  period (owner apps + monthly actuals ≤ T) and score APE/bias vs realized; calibration multiplier =
  `(1/(1+MAPE))` normalized to mean 1.0. (TWN run: burn_rate MAPE ~1.2 → down-weighted; commitment/
  owner/cpi MAPE ~0.07–0.13 → up-weighted.)
- **Confidence:** calibrated 0–1 from signal density, inter-model agreement, recency, and burn
  stability, with ranked drivers and a band.
- **Adequacy:** ERP `projected_costs` vs `model_reconciled_eac` with the $25k AND 10% gate →
  `likely_low` / `adequate` / `likely_high` / `indeterminate` + severity.

## Local-Ollama advisory layer (`--with-llm`)

Optional. For the material / review_required / high-divergence / adequacy-gap subset (cap 60), a local
model (default `qwen2.5:14b`, temp 0 + fixed seed) explains the deterministic numbers (rationale, top
risks, review questions, ambiguous-mapping suggestion). Strictly advisory: prompts carry only numeric
facts, outputs are JSON-validated, **safety-scanned fail-closed to a deterministic template**, and
hash-receipted. The LLM never produces a recommended number. Default (no `--with-llm`) uses the
deterministic templates so the whole package is reproducible offline.

## Guardrails

Accounting actuals are never overridden; every EAC ≥ actual-to-date; the advisory model number never
overwrites the authoritative rule-based recommendation; no fuzzy matching; Decimal-only money;
schedule %-complete ≠ cost %-complete. The quantitative core is byte-deterministic; the `llm/` outputs
are advisory and excluded from the determinism gate.

## Run

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-accuracy --project tropical [--with-llm]
```

Conclusion: `forecast_accuracy_ready` / `forecast_accuracy_ready_with_review_items` /
`forecast_accuracy_not_ready`.
