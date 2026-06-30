# Dependency reconciliation — Phase 4 prerequisite

## Base

- **Worktree:** `/Users/bobbyfetting/hb-personal-assistant-worktrees/feature/project-schedule-import-ux-20260630T204437Z`
- **Branch:** `feature/project-schedule-import-ux-20260630T204437Z`
- **Base `origin/main` SHA:** `ca7cc527f2cd83f039171549c311fda5b658e406`

## Prior commits on main (already present)

| SHA | Message |
|-----|---------|
| `3a84aab2` | fix(schedule): merge equivalent schedule package files canonically |
| `a787d709` | fix(schedule): audit cpm recompute after canonical imports |

## Missing from main — reconciled via cherry-pick

| SHA | Message | Action |
|-----|---------|--------|
| `f2a2356e` | fix(schedule): propagate as-of context consistently | Cherry-picked cleanly → `feb345c8` on Phase 4 branch |

**Note:** Phase 4 branch contains an **unmerged dependency** relative to `origin/main` until `fix(schedule): propagate as-of context consistently` is merged to main.

Phase 3 branch tip `89efc17a` is docs-only closeout; only `f2a2356e` was cherry-picked.

## Cherry-pick

- **Result:** Clean apply, no conflicts
- **Commit on branch:** `feb345c8` — `fix(schedule): propagate as-of context consistently`

## Dependency validation gate (all PASS)

| Gate | Result |
|------|--------|
| `pytest -k as_of` (hub API) | 5 passed |
| `pytest test_schedule_cpm_import_observability` | 11 passed |
| `pytest test_project_schedule_import_pipeline` | 9 passed |
| `py_compile` analytics | PASS |
| `scripts/test-schedule.sh` | 323 passed |
| `npm run typecheck` | PASS |
| `vitest scheduleApiAsOf` | 2 passed |
