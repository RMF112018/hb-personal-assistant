# Phase 13 Repo-Truth Audit

**Proof type:** repo truth  
**Timestamp:** 2026-07-01T09:04:10Z  
**Base commit:** `bc240b38` (origin/main — PR #245 Phase 12 merged)

## Phase 12 gate — PASS

Evidence on main: `docs/evidence/project-schedule-hub/baseline-pm-readiness-phase12-20260701T081419Z/`

Confirmed concepts:
- `scheduleBaselineLabels.ts` helpers
- Schedule Controls comparison context line
- Named Workbench read-only amber banner
- Driver Detail PM title hierarchy
- Phase 11 query-param driver routes intact

## Unique key audit (amendment 1)

**Real DB inspection** (`hb-personal-assistant.sqlite` @ schema v96):

| Object | Type | Droppable? |
|--------|------|------------|
| `review_item_id` PRIMARY KEY | table constraint | N/A |
| `idx_project_schedule_review_items_version_key` | **named UNIQUE INDEX** | **Yes** (`DROP INDEX`) |
| `sqlite_autoindex_project_schedule_review_items_1` | PK autoindex only | N/A |

**Conclusion:** The `(project_key, schedule_version_key, stable_item_key)` uniqueness is **not** a table-level UNIQUE constraint. It could be replaced in-place without a table rebuild.

**Design choice (amendment 2):** Despite droppable index, Phase 13 uses a **separate** `project_schedule_named_baseline_review_items` table because:
1. Zero mutation of `project_schedule_review_items` and its carry-forward/upsert paths
2. `prior_update` behavior remains byte-for-byte on existing code paths
3. PATCH isolation is explicit (ID prefix + separate repository)
4. V97 migration is purely additive (no index drop on live prior_update data)

Rehearsal on copied DB will validate V97 additive migration before real DB apply.

## Review persistence model (prior_update)

**Table:** `project_schedule_review_items` (V91)  
**Events:** `project_schedule_review_item_events` (V92)  
**Unique key:** `(project_key, schedule_version_key, stable_item_key)` via named index

**Fields:** `review_status` (open/reviewed/dismissed/watching), `pm_notes`, `evidence_json`, `source_activity_id`, operator/audit timestamps

**Sync:** `ProjectScheduleReviewService.sync_and_list` only persists when `comparison_basis == "prior_update"` (`use_persisted=True` only for prior_update branch)

**Carry-forward:** `upsert_review_item` inherits status from **unscoped** `(project_key, stable_item_key)` lookup; `_merge_candidate` uses unscoped `get_latest_review_item_by_stable_key`

**prior_update identity:** `project_key + schedule_version_key + stable_item_key` (no comparison_basis column)

## Legacy generic baseline

**Repo truth:** `sync_and_list` does **not** sync legacy `baseline` (`synced_count == 0` on POST). Workbench uses preview merge with `carry_forward_disposition=True` but **no persistence**. Test: `test_post_legacy_baseline_preserves_preview_only_behavior`.

**Phase 13:** Keep legacy `baseline` read-only/preview-only.

## Named baseline model (V96)

**Table:** `project_schedule_named_baseline_slots`  
**Identity:** `project_key + slot_key` (active row), `selection_id`, `schedule_version_key`, `selected_by/at`

**Resolution:** `ProjectScheduleNamedBaselineService.resolve_slot_for_controls` → `baseline_not_selected` / `baseline_invalid` explicit errors

## Named workbench current behavior (read-only)

- `build_review_items`: `named_preview=True` → `carry_forward_disposition=False`, forces `synced=false`, `read_only_baseline_preview=true`
- `sync_review_workbench`: raises `named_baseline_sync_not_supported` for `source_model == "named_slot"`
- API POST returns 400 `named_baseline_sync_not_supported`
- Frontend: `canSyncWorkbench = canSync && !namedPreview`; read-only banner

**Isolation proof:** `test_review_items_named_skips_disposition_carry_forward` — prior_update persisted `driver:DRV-A` does not appear in named workbench with disposition.

## Frontend workbench

- Sync on load only when `canSyncWorkbench` (not named)
- PATCH via `patchProjectScheduleReviewItem` by `review_item_id`
- Named slot selector from baselines query; missing/invalid disables context

## Test coverage gaps

- No named sync/patch persistence tests
- Frontend expects named workbench NOT to sync
- No PATCH cross-scope isolation tests
- No migration rehearsal tests

## Files expected to change

- `src/hb_assistant/store/project_schedule_named_baseline_review_tables.py` (new)
- `src/hb_assistant/store/project_schedule_named_baseline_review_repository.py` (new)
- `src/hb_assistant/construction/analytics/project_schedule_named_baseline_review_service.py` (new)
- `src/hb_assistant/construction/analytics/project_schedule_summary_service.py`
- `src/hb_assistant/construction/analytics/project_schedule_review_service.py` (PATCH dispatch only)
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/store/migrator.py`
- `tests/test_project_schedule_named_baseline_dispositions.py` (new)
- `tests/test_project_schedule_named_baseline_workbench.py`
- `frontend/src/pages/ProjectScheduleWorkbenchPage.tsx`
- `frontend/src/pages/ProjectScheduleWorkbenchPage.test.tsx`

## Files explicitly out of scope

- Parser, CPM, import pipeline, trend analytics, schedule source files
- `project_schedule_named_baseline_repository.py` selection semantics
- V90 legacy baseline model sync
- `project_schedule_review_items` schema (unchanged)

## Real DB plan

- Path: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Backup before migration; rehearse on copy first
- Tropical named slots selected (TWNU07/18/14 proof target)

## Risk register

| Risk | Mitigation |
|------|------------|
| PATCH affects wrong queue | ID prefix routing + isolation tests |
| Unscoped lookup leaks disposition | Separate repo; scoped queries only |
| prior_update regression | No changes to prior_update upsert/list |
| Migration on live DB | Copy rehearsal + backup + integrity_check |
