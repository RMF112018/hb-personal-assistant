# Phase 4 readiness evidence — External-Forecast Evaluation (flagship)

Stamp: 20260620T180000Z · Branch: `feature/forecast-ui-phase4-external-eval`
(off `feature/forecast-ui-phase3-run-center` @ 7fd66a74)

This bundle records the verified pre-implementation truth for the External-Forecast Evaluation
phase (plan §11, Product Phase H), captured before any code change.

## Verified facts
- **Live DB schema_version = 60** (read-only, `mode=ro`); WAL = 0 bytes. See `db_schema_version.txt`.
- **All 8 v61 target tables ABSENT** from the live DB (`forecast_external_forecasts`,
  `forecast_external_forecast_rows`, `forecast_external_forecast_mappings`,
  `forecast_accuracy_results`, `forecast_comparison_results`, `forecast_anomaly_findings`,
  `forecast_review_items`, `forecast_evidence_packages`).
- **Schema version is v61, not the plan-file's notional v64** — v61–v63 placeholders were skipped.
  `LATEST_SCHEMA_VERSION` is currently 60; this phase bumps it to 61.
- **Lifecycle contract `table_count = 391`**; bumping to 399 (+8) requires updating the contract
  JSON plus **16 `== 391` assertions across 15 test files**. See `count_assert_sites.txt`.
- **Deps present in venv**: `openpyxl 3.1.5` (xlsx parsing) and `fastapi 0.136.3`; **no
  `python-multipart`** → upload is base64-in-JSON. All commands use `.venv/bin/python`.
- **No CFR edits planned** — comparison/metrics live in the hb_assistant analytics layer; CFR
  `forecast_accuracy` adequacy/banding are design references only.

## Files
- `git_state.txt` — branch + recent commits.
- `db_schema_version.txt` — live DB schema version, v61-table absence, WAL bytes (mode=ro).
- `count_assert_sites.txt` — the 16 `== 391` sites + contract JSON to move in lockstep.
- `venv_deps.txt` — openpyxl / fastapi presence; python-multipart absence.
