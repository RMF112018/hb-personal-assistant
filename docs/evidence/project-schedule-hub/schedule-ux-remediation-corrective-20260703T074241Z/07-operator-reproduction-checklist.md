# Operator reproduction checklist

## Safety confirmations

- [x] Copied DB only — not Application Support live path
- [x] No live schedule imports
- [x] No Obsidian vault writes
- [x] No push / no PR
- [x] No CPM engine or formula changes

## Copied DB

**Path:** `/tmp/hb-pa-schedule-ux-final/hb-pa-schedule-ux-20260702T160500Z.sqlite`

Prove not live:

```bash
echo "$HB_ASSISTANT_DB_PATH"
# Must NOT match ~/Library/Application Support/hb-personal-assistant/...

sqlite3 "$HB_ASSISTANT_DB_PATH" "SELECT COUNT(*) FROM schedule_file_imports WHERE project_key='tropical';"
```

## Environment

```bash
cd /Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-ux-nav-polish-20260702T154747Z
source /Users/bobbyfetting/hb-personal-assistant/.venv/bin/activate
export PYTHONPATH="$PWD/src:$PWD/subrepos/construction-financial-review/src"
export HB_ASSISTANT_DB_PATH="/tmp/hb-pa-schedule-ux-final/hb-pa-schedule-ux-20260702T160500Z.sqlite"
```

## Start backend (copied DB only)

```bash
python scripts/dev_schedule_clean_db_backend.py \
  --db-path "$HB_ASSISTANT_DB_PATH" \
  --port 8000 \
  --confirm-clean-copy \
  --allow-custom-copy-path
```

Verify health:

```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
# Expect: db_path_is_live_db: false, clean_copy_guard_passed: true
```

## Start frontend

```bash
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

## URLs to open

| URL | Expected visible state |
|-----|------------------------|
| http://127.0.0.1:5173/projects/tropical/schedule?as_of=2026-06-22 | Primary Actions with Manage Baselines; CPM reason-aware "not computed" for TWNU18-era version |
| http://127.0.0.1:5173/projects/tropical/schedule?as_of=2026-06-29 | CPM available; trends render or show reason-aware empty (not loading flicker) |
| http://127.0.0.1:5173/projects/tropical/schedule/baselines?as_of=2026-06-22 | Baseline selector as primary surface |
| http://127.0.0.1:5173/projects/tropical/schedule/import | Import page; no `as_of` required |
| http://127.0.0.1:5173/projects/tropical/schedule/workbench?as_of=2026-06-29 | Workbench loads |

## Change `as_of` refresh test

1. Open `?as_of=2026-06-22`, wait for load
2. Change URL to `?as_of=2026-06-29`
3. Expect **"Refreshing schedule data…"** banner (`data-testid="schedule-refreshing-banner"`) before final labels
4. Expect no premature "Trend data not available" during fetch

## Screenshots

Captured under:

`docs/evidence/project-schedule-hub/schedule-ux-remediation-corrective-20260703T074241Z/screenshots/`

Regenerate (waits for API + loaded markers before each capture):

```bash
python scripts/dev_schedule_ux_corrective_screenshots.py \
  --out-dir docs/evidence/project-schedule-hub/schedule-ux-remediation-corrective-20260703T074241Z/screenshots
```

Proof manifest: `screenshot-loaded-state-proof.json` in the evidence package root.

## API payload evidence

`docs/evidence/project-schedule-hub/schedule-ux-remediation-corrective-20260703T074241Z/api-payloads/`

## CPM recompute

**Not run.** SQL audit shows CPM runs present for `tropical|1071|2026-06-23 08:00`; recompute gate not satisfied for masking. See `01-copied-db-cpm-trend-audit.md`.

## Tests

```bash
cd frontend
npm run test -- --run src/pages/ProjectSchedulePage.test.tsx src/lib/scheduleDataState.test.ts src/components/projects/ProjectWorkspaceNav.test.tsx
```

## Confirm no live DB in use

```bash
lsof -p $(lsof -tiTCP:8000 -sTCP:LISTEN) 2>/dev/null | grep sqlite
# Should show /tmp/hb-pa-schedule-ux-final/... not Application Support
```
