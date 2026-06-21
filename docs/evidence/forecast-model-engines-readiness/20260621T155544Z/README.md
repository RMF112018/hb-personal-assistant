# Model-Engines Readiness — live read-only evidence (2026-06-21)

Go/no-go evidence for the deferred statsforecast 7th-estimator PR (Phase I). Produced by
`construction-financial-review` CLI `model-engines-readiness` (ADR 285) — read-only.

- **Context package:** `…/phase15-db-certified-final-output-20260619T073808Z/guarded/readiness/file/forecast_context_package_tropical_db-certified-final-output-20260619T073808Z` (1081 monthly-actuals rows).
- **DB (semantic gates, read-only):** live `hb-personal-assistant.sqlite` (v61). `mode=ro`; size + mtime + WAL/SHM identical before and after (`live_db_readonly_fingerprint.json`).
- **CLI rc:** 0.

## Decision: `model_engines_data_ready`

The real tropical data is **both** time-series-sufficient AND semantically safe — a clear GO for the
statsforecast investment, with the deterministic 6-estimator ensemble as the fallback for the 21
short-history codes.

### Time-series sufficiency
- 108 codes, all with actuals. **87 statsforecast-eligible** (≥3 clean completed months); 44 with ≥12 months.
- **Code coverage 80.6%; dollar coverage 89.2%** ($6,766,317.43 of $7,588,392.14 cost-to-complete).
- 21 codes fall back to the existing ensemble (short history).
- Data quality: 0 all-zero, 0 single-spike, 0 source-contaminated; 59 with interior gaps, 7 with
  negative/credit months (both reported, neither disqualifying).

### Semantic safety (forecasting gates, mode=warn)
- **0 errors** across all 5 gates → no hard fail. 395 advisory warnings carried (not blocking):
  387 double-count (lifecycle-precedence advisories), 6 budget-dynamic-columns, 1 projection-parity,
  1 cost-type-guard.
- Known projection-parity limits carried as warnings: RFQ scope mismatch; prime change-order
  line-item fan-out.
- Catalog versions: semantic_catalog v1, actuals_precedence_model v2.
- Actuals basis: CostEntries monthly to date (precedence #1); `actual_cost` (100% null) never used;
  ERP sidecar compare-only; terminal/dynamic budget columns never treated as features.

## Files
- `model_engines_readiness_report.json` — full deterministic report.
- `live_db_readonly_fingerprint.json` — live-DB no-mutation proof.
