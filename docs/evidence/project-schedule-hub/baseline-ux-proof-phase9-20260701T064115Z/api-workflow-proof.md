# API Workflow Proof

**Proof type:** fixture DB (TestClient)  
**Project:** tropical  
**as_of:** 2026-07-03

## Results

| Check | Result |
|---|---|
| GET /schedule/baselines (3 slots) | PASS — `api-baselines-get.json` |
| PUT current_contract_baseline | PASS — `api-baselines-put.json` |
| GET controls named | PASS — `api-controls-current-contract-baseline.json` |
| GET review-items named | PASS — `api-workbench-current-contract-baseline.json` |
| GET driver named | PASS — `api-driver-current-contract-baseline.json` |
| Missing named baseline | PASS — `api-missing-baseline.json` (`baseline_not_selected`) |
| POST named sync | PASS — `400 named_baseline_sync_not_supported` |
| Unknown controls basis | PASS — `400 invalid_comparison_basis` — `api-controls-invalid-comparison-basis.json` |

## Cross-surface slot alignment

After PUT, controls `baseline_schedule_version_key`, workbench `baseline_context.schedule_version_key`, and driver `baseline_context.schedule_version_key` all resolve to `tropical|S1|2026-06-01`.

## Controls no-silent-fallback (Phase 9 amendment)

`GET /schedule/controls?comparison_basis=mystery_basis` returns HTTP 400 with `detail: invalid_comparison_basis` — no prior_update payload returned.
