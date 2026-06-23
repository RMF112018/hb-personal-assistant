# P1 Evidence — Forecast output header totals + prior-run deltas

Generated: P1-header-totals-20260623T092610Z  ·  Branch: feature/forecast-output-header-totals-p1  ·  No live-DB mutation (live read read-only).

## BEFORE — live DB (read-only), pre-P1
`01-live-header-null-audit-BEFORE.json`: 1 forecast_outputs row, **all 5 header fields NULL** (Gap 1/7), while 94/127 per-code recommended_projected_cost are populated.

## AFTER — P1 code, real analysis package projected into a temp v63 DB
`02-temp-db-header-null-audit-AFTER.json` (real package `forecast_analysis_package_tropical_crosswalk_v2_20260617_152654`):
- Run 1 (output_id `fout-af66495a0388ca4dc80f9653039a44b2` — the SAME id as the live row):
  estimated_final_cost = forecast_at_completion = **33049244.52**, cost_to_complete = **5450096.56**,
  variance_to_budget = **-22607715.19** (EAC − Σ budget_amount). variance_to_prior_forecast NULL (no prior run) → null_count 1 (legitimate).
- Run 2 (perturbed +1,000,000 on one code, prior run = run 1): **all 5 populated**, variance_to_prior_forecast = **1000000.00** (nonzero), and a project-level `current_vs_prior` change row links prior_run_id `p1-run-1` (`03-current-vs-prior-change-rows.json`).

## Acceptance
- Header totals = Decimal aggregates of per-code values (no float). ✅
- variance_to_budget = header EAC − budget sum. ✅
- prior delta populated when a prior run exists; NULL on first run. ✅
- DB↔package parity proven on both apply runs (raw_json-only; header totals are columns). ✅
- No output/export package generated; persistence is DB-only. ✅

Reproduce: project the real analysis package with `project_run_output(..., apply=True, db_path=<temp>)` under PYTHONPATH=src; the header aggregate depends only on the recommendations file, so a temp v63 DB yields the same header the live row gets on re-projection.
