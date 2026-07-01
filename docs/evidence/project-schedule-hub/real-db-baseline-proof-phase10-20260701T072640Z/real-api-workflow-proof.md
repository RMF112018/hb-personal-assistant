# Real API Workflow Proof

**STAMP:** 20260701T072640Z  
**Proof type:** real local DB + real API

## Results

| Check | Status | Artifact |
|-------|--------|----------|
| Controls Current Contract Baseline | PASS | `api-real-controls-current-contract-baseline.json` |
| Controls Previous Progress Update | PASS | `api-real-controls-previous-progress-update-baseline.json` |
| Controls Secondary Progress Update | PASS | `api-real-controls-secondary-progress-update-baseline.json` |
| Workbench named context | PASS | `api-real-workbench-current-contract-baseline.json` |
| Driver detail named context | PASS | `api-real-driver-current-contract-baseline.json` (activity `FM-PERMPOWER`) |
| Named sync rejected | PASS 400 | `api-real-named-sync-rejected.json` |
| Invalid controls basis | PASS 400 | `api-real-invalid-controls-basis.json` |

## Cross-surface alignment (Current Contract Baseline)

All surfaces report `baseline_context.schedule_version_key` = `tropical|815|2025-08-07 08:00` and `slot_key` = `current_contract_baseline`.

## Controls links

`review_workbench` link includes `comparison_basis=current_contract_baseline` and `as_of=2026-07-01`.

## Known limitation

Activity IDs containing `/` (e.g. `FAB/DEL-10`) return HTTP 401 via live API path routing; driver proof uses `FM-PERMPOWER` which succeeds. UI encodes paths correctly for simple IDs.

## No silent fallback

`mystery_basis` returns `400 invalid_comparison_basis` — no prior_update payload.
