# Repo-Truth Audit

**STAMP:** 20260701T072640Z  
**BRANCH:** ops/schedule-real-db-baseline-proof-phase10-20260701T072640Z  
**WORKTREE:** /Users/bobbyfetting/hb-personal-assistant-worktrees/ops/schedule-real-db-baseline-proof-phase10-20260701T072640Z  
**EVIDENCE:** docs/evidence/project-schedule-hub/real-db-baseline-proof-phase10-20260701T072640Z  
**origin/main SHA:** c9482c9a3ef6e5c8eda4fc776ec55a3fe90c3d7b (PR #240 Phase 9)

## Phase 9 gate

PASS — verified on `origin/main`:
- `frontend/src/lib/scheduleBaselineLabels.ts`
- `validate_controls_comparison_basis` in `project_schedule_baseline_vocabulary.py`
- Workbench `setSearchParams` in `ProjectScheduleWorkbenchPage.tsx`
- Phase 9 evidence bundle present

## Schema / migration

| Item | Value |
|------|-------|
| `LATEST_SCHEMA_VERSION` | 96 (`migrator.py`) |
| v96 migration name | `v96_project_schedule_named_baseline_slots` |
| Table | `project_schedule_named_baseline_slots` |
| Version tracking | `schema_migrations` (`MAX(version)`), not `PRAGMA user_version` |

**Migration entry points:**
1. `SQLiteMigrator(db_path).apply()` — recommended for Phase 10
2. `ensure_schedule_schema()` on schedule API use
3. `POST /api/admin/schema/migrate` (admin role)

## API route map (`/api/projects/{project_key}`)

| Route | Behavior |
|-------|----------|
| `GET/PUT /schedule/baselines` | Named slot state; PUT requires operator |
| `GET /schedule/controls` | `comparison_basis` default `prior_update`; unknown → 400 `invalid_comparison_basis` |
| `GET /schedule/review-items` | Workbench read; named → read-only preview |
| `POST /schedule/review-items` | Named basis → 400 `named_baseline_sync_not_supported` |
| `GET /schedule/drivers/{activity_id}/detail` | Named `comparison_basis` / legacy `basis` |

## Frontend surfaces

| File | Role |
|------|------|
| `scheduleBaselineLabels.ts` | Labels, `workbenchHref`, `driverDetailHref` |
| `ProjectSchedulePage.tsx` | Hub, Baseline Anchors, controls basis state |
| `ScheduleBaselineSelector.tsx` | PUT baselines |
| `ScheduleControlsPanel.tsx` | 4-way comparison, deep links |
| `ProjectScheduleWorkbenchPage.tsx` | Named read-only; URL `comparison_basis` sync |
| `ProjectScheduleDriverDetailPage.tsx` | Humanized basis labels |

**UI routes:** `/projects/tropical/schedule`, `/schedule/workbench`, `/schedule/drivers/:activityId`

## Expected real DB writes

1. v96 DDL only (additive `project_schedule_named_baseline_slots`)
2. Three `PUT /schedule/baselines` slot selections for tropical (reversible via PUT null or clear)

**Out of scope:** schedule imports, parsed data, CPM, V90 sync, disposition persistence.

## Rollback plan

1. Stop backend/frontend
2. Restore from `db-backup/hb-personal-assistant.logical-backup.pre-phase10.sqlite`
3. Restore wal/shm sidecars if copied

## Files expected to change

- Evidence under `real-db-baseline-proof-phase10-20260701T072640Z/` only (unless proof failure)
- Optional evidence capture script in evidence dir

## Risks

- Real DB backup may be large (not committed)
- `frontend/src/lib/` gitignored — force-add if code fixes needed
- Local DB may be pre-v96 (Phase 9 inventory: named slots table absent)

## Proof plan

1. Backup → inventory → migrate v96 → select tropical baselines via API → API workflow JSON → live UI → validation → evidence commit
