# Legacy V90 Baseline Model vs Phase 7 Named-Slot Baseline Model

## Legacy model (V90 — unchanged)

| Aspect | Detail |
|---|---|
| Table | `project_schedule_baseline_selections` |
| Unique key | `(project_key, current_schedule_version_key)` where `selection_status='active'` |
| Semantics | One user-selected baseline **per current schedule version** |
| API | `GET/PUT /api/projects/{project_key}/schedule/baseline` (singular) |
| Service | `ProjectScheduleSelectedBaselineService` |
| Consumers | Hub `baseline_summary`, Review Workbench `comparison_basis=baseline`, Phase 6 controls `comparison_basis=baseline` (legacy BC) |
| Fields | `current_schedule_version_key`, `selected_baseline_schedule_version_key`, `selection_note`, `selected_by_operator` |

When the current schedule version advances, the operator may need a new legacy selection for workbench baseline comparison.

## Phase 7 named-slot model (v96 — new)

| Aspect | Detail |
|---|---|
| Table | `project_schedule_named_baseline_slots` |
| Unique key | `(project_key, slot_key)` where `is_active=1` |
| Semantics | Up to **three project-level named anchors** independent of which version is “current” |
| Slots | `current_contract_baseline`, `previous_progress_update_baseline`, `secondary_progress_update_baseline` |
| API | `GET/PUT /api/projects/{project_key}/schedule/baselines` (plural) |
| Service | `ProjectScheduleNamedBaselineService` |
| Consumers | Schedule Controls named `comparison_basis` values only |
| Validation | Prior schedule versions only; cannot select current/as-of version; no duplicate version across active slots (post-update state) |

## Boundary rules

1. **No automatic sync** between V90 legacy selection and named slots in Phase 7.
2. **No silent fallback** from named slot to `prior_update` or legacy `baseline`.
3. **Review Workbench** continues to use V90 + generic `baseline` only.
4. **Controls UI** exposes `prior_update` + three named slots; generic `baseline` hidden from primary UI but accepted on API for backward compatibility.
5. **Workbench deep links** from named-baseline controls are omitted (workbench cannot compare named slots).

## Migration path (future, out of Phase 7 scope)

Optional later phase could bridge `current_contract_baseline` slot to V90 legacy selection for workbench parity.
