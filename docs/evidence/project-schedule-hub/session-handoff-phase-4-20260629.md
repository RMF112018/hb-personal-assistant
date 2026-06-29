# Project Schedule Hub Phase 4 — Session Handoff

**Date:** 2026-06-29  
**Repo:** `/Users/bobbyfetting/hb-personal-assistant`  
**HEAD at handoff:** `b1840fc2` — `fix(schedule): correct project schedule change-impact comparison`  
**Working tree:** Uncommitted Phase 1–4 schedule-hub work (see §4). No commit landed for Phase 4 in this session.  
**Schema:** V91 (`LATEST_SCHEMA_VERSION = 91`) — `project_schedule_review_items` via `v91_project_schedule_review_workbench`

## 1. Session objective

Complete **Phase 4 — Schedule Analysis Workbench & PM Action Workflow** after Phases 1–3 (change-impact fix, schedule trust/baseline/drilldowns, driver analysis).

Phase 4 deliverables implemented in working tree:

| Area | Status |
|------|--------|
| V91 review persistence | Done — `project_schedule_hub_tables.py`, migrator, repository |
| Review service (queue sync + preview) | Done — `project_schedule_review_service.py` |
| Memo export (Markdown/HTML) | Done — `project_schedule_memo_service.py` |
| Baseline + prior driver bases | Done — `build_hub_analysis()` in driver service |
| Driver detail panel API | Done — `build_driver_detail()` + `GET .../drivers/{id}/detail` |
| Review workbench API | Done — `GET/POST/PATCH .../review-items` |
| Export API | Done — `GET .../schedule/export?format=markdown\|html` |
| Hub wire (`review_workbench`, dual-basis drivers) | Done — summary service |
| Frontend workbench + driver detail routes | Done — new pages + schedule hub links |
| Tests | Done — `test_project_schedule_review_workbench.py`; hub/driver regressions green |

**Not done this session:** Phase 4 evidence bundle (validation-suite.txt, closeout note), commit/PR, live TWNU18→TWNU19 regression proof run on production DB, workbench frontend tests.

## 2. Architecture decisions (carry forward)

1. **Hub reads are read-only.** `build_summary` calls `build_preview()` only — no `upsert_review_item` on GET.
2. **Persistence is operator-gated.** `POST /api/projects/{project_key}/schedule/review-items` runs `sync_review_workbench()` → `sync_and_list()`.
3. **Stable item keys** carry disposition across updates: `driver:{id}`, `milestone:{id}`, `negative_float:{id}`, `worsened_float:{id}`, `critical:{id}`.
4. **`change_driver_analysis` hub shape** is now `{ available, advisory_posture, prior_update, baseline }`. Story/narrative uses `prior_update`. Frontend must read nested `prior_update` (dashboard updated; tests updated).
5. **Baseline drivers:** When selected baseline key equals prior update key, baseline analysis reuses prior results with `comparison_basis: baseline`.
6. **Public envelopes** strip `schedule_version_key` / `project_key` from workbench items to satisfy PM no-raw-id guardrails.
7. **`as_of` matters.** Seeded July schedule data requires `as_of=2026-07-03` (or later) on review sync/detail APIs when “today” is before data dates.

## 3. API surface (Phase 4)

| Method | Path | Role |
|--------|------|------|
| GET | `/api/projects/{key}/schedule/review-items` | viewer — read-only preview |
| POST | `/api/projects/{key}/schedule/review-items?as_of=` | operator — sync + persist |
| PATCH | `/api/projects/{key}/schedule/review-items/{id}` | operator — disposition/notes |
| GET | `/api/projects/{key}/schedule/drivers/{activity_id}/detail?comparison_basis=&as_of=` | viewer |
| GET | `/api/projects/{key}/schedule/export?format=markdown\|html&as_of=` | viewer — attachment download |

Existing Phase 2–3 routes unchanged: `/schedule`, `/drilldowns`, `/drivers`, `/baseline`.

## 4. Key files (uncommitted)

**New**

- `src/hb_assistant/construction/analytics/project_schedule_review_service.py`
- `src/hb_assistant/construction/analytics/project_schedule_memo_service.py`
- `frontend/src/pages/ProjectScheduleWorkbenchPage.tsx`
- `frontend/src/pages/ProjectScheduleDriverDetailPage.tsx`
- `tests/test_project_schedule_review_workbench.py`

**Modified (Phase 4 touch)**

- `src/hb_assistant/construction/analytics/project_schedule_driver_analysis_service.py` — hub analysis, driver detail
- `src/hb_assistant/construction/analytics/project_schedule_summary_service.py` — workbench preview, export/sync helpers
- `src/hb_assistant/construction/analytics/api.py` — new endpoints
- `src/hb_assistant/store/project_schedule_hub_repository.py` — review CRUD (started pre-session)
- `src/hb_assistant/store/project_schedule_hub_tables.py` — V91 (started pre-session)
- `src/hb_assistant/store/migrator.py` — V91 migration
- `frontend/src/pages/ProjectSchedulePage.tsx`, `api.ts`, `routes.tsx`, `ProjectSchedulePage.test.tsx`

**Also dirty from Phases 1–3** (same branch, not yet committed): trust service, drilldown service, comparison module, hub tests, phase 2–3 evidence folders.

## 5. Validation status (last run this session)

```bash
python -m pytest tests/test_project_schedule_review_workbench.py \
  tests/test_project_schedule_driver_analysis.py \
  tests/test_project_schedule_hub_api.py -q
# 22 passed

cd frontend && npm test -- ProjectSchedulePage.test.tsx --run
# 5 passed
```

### TWNU non-regression numbers (must hold after commit)

When validating against live TWNU18→TWNU19 fixture with `as_of=2026-07-03`:

- 461 later / 76 earlier / 537 changed / 98 new / 378 worsened / 122 improved / 6 milestones
- Forecast 2026-11-03 @ 0 days
- 712 remaining / 711 source negative float / 613 CPM critical

Re-run hub API tests and populated comparison fixture after commit.

## 6. Residual work / next session

1. **Commit stack** — Stage Phase 1–4 schedule-hub files only; avoid unrelated `ScheduleIdentityReviewPage.tsx` unless intentional.
2. **Phase 4 evidence bundle** — `docs/evidence/project-schedule-hub/phase-4-schedule-workbench-<timestamp>/` with:
   - `notes/phase-4-closeout.md`
   - `tests/validation-suite.txt`
   - `tests/frontend-project-schedule-page.txt`
   - optional API sample JSON (redacted)
3. **Frontend tests** — `ProjectScheduleWorkbenchPage.test.tsx` (sync + disposition smoke).
4. **`as_of` UX** — Pass schedule hub `as_of_date` into workbench sync/export/detail calls (today defaults break July-seeded dev data).
5. **Operator role gate** — Workbench auto-sync on load requires operator role; viewer sees preview-only path or messaging.
6. **PDF export** — Deferred; Markdown/HTML only.

## 7. Handoff instructions for next agent

1. Confirm working tree: `git status --short` and diff scope vs this handoff.
2. Re-run validation block in §5 before any new edits.
3. Run TWNU regression proof if touching comparison/driver/review paths.
4. On closeout: write Phase 4 evidence folder; do **not** classify as vault lifecycle package (evidence bundle only per `vault-package-governance`).
5. Preserve advisory language everywhere — sequence cues, not causation.

## 8. Vault package governance

- Project Schedule Hub work is **repo-truth** with evidence under `docs/evidence/project-schedule-hub/**`.
- Evidence bundles are **not** lifecycle packages; no `Package Registry.md` entry required for Phase 4.
- Keep evidence in-repo; reference from closeout notes only; no secret/token artifacts.