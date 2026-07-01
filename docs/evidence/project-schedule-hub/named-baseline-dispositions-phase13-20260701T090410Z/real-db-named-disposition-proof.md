# Phase 13 Real DB Named Disposition Proof

**Proof type:** real local DB + real API  
**Timestamp:** 2026-07-01T09:32:57Z  
**Project:** tropical

## Steps executed

1. GET `current_contract_baseline` workbench — unsynced/preview candidates before operator POST
2. POST sync — materialized named-baseline items (`review_scope=named_baseline`, `synced=true`)
3. PATCH one `psnbri-*` item → `watching` + PM notes `phase13 real db proof`
4. GET confirms persisted disposition in named scope
5. GET `prior_update` — queue count **100** (unchanged scope)
6. GET `previous_progress_update_baseline` — separate scope (**100** preview items, no contract disposition leak)

## Summary (`real-db-proof-summary.json`)

- `review_scope`: `named_baseline`
- `synced`: `true`
- `patched_status`: `watching`
- prior_update and progress slot queries return independent queues

## Isolation

Named PATCH did not alter `project_schedule_review_items` prior_update rows (verified in fixture + real DB tests).
