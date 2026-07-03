# Runtime visual validation

**Capture method:** Playwright Chromium against `http://127.0.0.1:5173`  
**Script:** `scripts/dev_schedule_ux_corrective_screenshots.py` (run from repo root)  
**Loaded-state gate:** Each capture waits for the relevant GET API response (200), loading markers hidden, and page-specific ready selectors (see `screenshot-loaded-state-proof.json`).  
**`04` loading shot:** Changes the in-page As-of date input (not full navigation) while delaying the `as_of=2026-06-29` schedule API so `schedule-refreshing-banner` is visible with prior content retained.  
**Backend:** `scripts/dev_schedule_clean_db_backend.py` on port 8000  
**DB:** `/tmp/hb-pa-schedule-ux-final/hb-pa-schedule-ux-20260702T160500Z.sqlite`  
**Role:** `localStorage hb-ui-role=operator` injected before navigation  

All screenshots are real runtime captures from localhost — not design comps or static mocks.

## Screenshot manifest

| File | Route | Purpose |
|------|-------|---------|
| `01-overview-top-asof-2026-06-22.png` | `/projects/tropical/schedule?as_of=2026-06-22` | Overview top: PM story + Primary Actions |
| `02-schedule-dropdown-open-manage-baselines.png` | same + Schedule dropdown open | Manage Baselines visible in nav |
| `03-baseline-management-visible.png` | `/projects/tropical/schedule/baselines?as_of=2026-06-22` | Dedicated baseline management route |
| `04-asof-refresh-loading-state.png` | `as_of` 2026-06-22 → 2026-06-29 mid-fetch | Refreshing state during `as_of` change (API delay + `schedule-refreshing-banner`) |
| `05-post-refresh-trends-state-asof-2026-06-29.png` | `/projects/tropical/schedule?as_of=2026-06-29` | Settled state after refresh |
| `06-import-schedule-route.png` | `/projects/tropical/schedule/import` | Import route (no `as_of` dependency) |
| `07-review-workbench-route.png` | `/projects/tropical/schedule/workbench?as_of=2026-06-29` | Workbench readable |
| `08-driver-detail-empty-state.png` | `/projects/tropical/schedule/driver-detail` | Driver detail safe empty state |
| `09-activity-drivers-empty-state.png` | `/projects/tropical/schedule/drivers` | Activity drivers safe empty state |

## Acceptance proofs

- **Manage Baselines directly accessible:** screenshots 01, 02, 03
- **`as_of` refresh loading/refreshing:** screenshot 04 + vitest `schedule-refreshing-banner` assertions
- **Reason-aware CPM/trend states:** screenshot 05 (2026-06-29 with CPM available); 01 (2026-06-22 with reason-aware CPM-not-computed copy)
- **No live DB:** backend health reports `db_path_is_live_db: false` for copied path

## Regenerate

```bash
export HB_ASSISTANT_DB_PATH="/tmp/hb-pa-schedule-ux-final/hb-pa-schedule-ux-20260702T160500Z.sqlite"
python scripts/dev_schedule_clean_db_backend.py --db-path "$HB_ASSISTANT_DB_PATH" --port 8000 --confirm-clean-copy --allow-custom-copy-path
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
python scripts/dev_schedule_ux_corrective_screenshots.py \
  --out-dir docs/evidence/project-schedule-hub/schedule-ux-remediation-corrective-20260703T074241Z/screenshots
```
