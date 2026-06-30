# Legacy V90 vs Named Slot — Workbench Read-Path Boundary (Phase 8)

## Three source models

| source_model | comparison_basis | Storage | Resolver reads |
|---|---|---|---|
| `prior_update` | `prior_update` | N/A (previous version resolution) | `_resolve_previous` |
| `legacy_v90` | `baseline` | `project_schedule_baseline_selections` | `ProjectScheduleHubRepository.get_active_baseline_selection` |
| `named_slot` | `current_contract_baseline`, etc. | `project_schedule_named_baseline_slots` | `ProjectScheduleNamedBaselineRepository` |

## Phase 8 rules

1. **No cross-read:** `legacy_v90` resolver path must not query named slot table. `named_slot` path must not query V90 table.
2. **No silent fallback:** unknown basis → `invalid_comparison_basis`; missing named → `baseline_not_selected`; invalid named → `baseline_invalid`.
3. **Named workbench is read-only:** `use_persisted=False`, `synced=False`, no `sync_queue` for named basis.
4. **POST sync:** only `prior_update` may sync. Named → `400 named_baseline_sync_not_supported`. Legacy `baseline` POST behavior unchanged (no sync, preview only).
5. **Controls links:** reinstated for valid named slots only when workbench/driver routes resolve the same slot.

## Unchanged by Phase 8

- `GET/PUT /schedule/baseline` (singular, V90)
- `GET/PUT /schedule/baselines` (plural, named slots)
- V90 table schema and repository methods
