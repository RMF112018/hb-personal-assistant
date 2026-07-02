# 06-operator-validation-steps.md — Project Schedule UX Remediation (Exact Local Steps for Bobby)

**Stamp**: 20260702T154754Z  
**Worktree**: /Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-ux-nav-polish-20260702T154747Z  
**Branch**: fix/schedule-ux-nav-polish-20260702T154747Z  
**Evidence dir**: docs/evidence/project-schedule-hub/schedule-ux-remediation-20260702T154754Z

**CRITICAL**: Use copied DB only. Never point at live path for write-capable or browser validation. No imports during this run.

## 1. Prep (in terminal)
```bash
cd /Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-ux-nav-polish-20260702T154747Z || exit 1

# Activate (from original checkout venv as per procedure)
source /Users/bobbyfetting/hb-personal-assistant/.venv/bin/activate

unset PYTHONPATH
export PYTHONPATH="$PWD/src:$PWD/subrepos/construction-financial-review/src"

# Create + copy DB (NEVER the live one for the server)
mkdir -p /tmp/hb-personal-assistant-schedule-ux
cp "$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite" \
   "/tmp/hb-personal-assistant-schedule-ux/hb-personal-assistant-schedule-ux-$(date -u +%Y%m%dT%H%M%SZ).sqlite"

export HB_ASSISTANT_DB_PATH="/tmp/hb-personal-assistant-schedule-ux/hb-personal-assistant-schedule-ux-$(date -u +%Y%m%dT%H%M%SZ).sqlite"

echo "Using copied DB: $HB_ASSISTANT_DB_PATH"
# Verify it is not the live path
python -c "
import os
p = os.environ.get('HB_ASSISTANT_DB_PATH', '')
print('DB_PATH:', p)
print('Is under /tmp:', p.startswith('/tmp'))
assert '/Application Support' not in p, 'SAFETY: still pointing at live app support'
print('SAFETY OK')
"
```

## 2. Start backend (terminal 1, with copied DB)
Use explicit create_app so the copied path is honored (plain uvicorn --factory does not forward easily).
```bash
python -c '
import os, uvicorn
from hb_assistant.construction.analytics.api import create_app
db = os.environ.get("HB_ASSISTANT_DB_PATH")
print("Launching analytics API with db_path=", db)
uvicorn.run(create_app(db_path=db), host="127.0.0.1", port=8000, reload=False)
'
```
- Keep running. Confirm no errors about schema or missing tropical.

(Alternative if launcher supports: export the var and use launcher, but explicit is proven.)

## 3. Start frontend (terminal 2)
```bash
cd frontend
npm run dev
```
- Note the URL (usually http://localhost:5173).
- Vite proxies /api → 127.0.0.1:8000.

## 4. Browser validation steps (use the copied DB via the servers above)
1. Open http://localhost:5173/projects/tropical (or /projects/tropical/schedule directly).
2. Verify project header + subnav renders (Overview, Forecasting, **Schedule** (as dropdown trigger with ▼), Staffing, Exposures).
3. Click the Schedule trigger (or hover/focus + Enter). Verify dropdown menu appears with exactly:
   - Schedule Overview (href ends /schedule)
   - Import Schedule ( /schedule/import )
   - Review Workbench ( /schedule/workbench )
   - Driver Detail ( /schedule/driver-detail )
   - Activity Drivers ( /schedule/drivers )
4. With dropdown open or closed, navigate to Overview (click the Overview item or the Schedule Overview menu item). Verify the Schedule trigger shows active styling (accent tint) and aria-current.
5. From dropdown, click **Import Schedule**. Verify page loads (upload form / flow). Note "Back to Project Schedule" link. Use browser back or nav to return.
6. From dropdown, click **Review Workbench**. Verify page loads, review cards visible, actions present. Confirm Schedule group still appears active.
7. Return to Overview via subnav or dropdown. Verify:
   - Top: Schedule status/story headline + metrics (Forecast Finish etc).
   - Primary Actions row with prominent **Import Schedule** (Link), Open Review Workbench, Export Memo (if available), Manage Baselines note.
   - Baseline / Comparison Context section with labels + explanatory paragraph.
   - Where to Look First.
   - Controls Health (the old controls panel + baseline selector) appear lower.
   - Trends / charts section (title simplified).
   - Technical evidence at/near bottom (collapsed).
8. Click Import Schedule from Primary Actions. Confirm lands on import page.
9. On Overview, verify no "source-export negative float" jargon in primary metrics (should be neutral "negative float remaining").
10. If any WBS rows: "Not provided" displayed (hover/title may show old reason).
11. Open a driver from "Where to Look First" table link → lands on driver detail (with activity).
12. Manually visit /projects/tropical/schedule/drivers (no id) and /schedule/driver-detail (no id). Verify friendly "Activity Drivers" index/empty state with guidance + back links (no crash, no "requires activityId").
13. Verify active Schedule state on all the above nested routes.
14. (Optional) Test keyboard: Tab to Schedule button, Enter to open, Tab through menu items, Esc to close.

## 5. Capture screenshots
- Use browser devtools or full window capture for the 8+ required (see 02-screenshot-inventory.md).
- Name per convention in screenshots/.
- If using the python capture helper from prior evidence, set the same DB_PATH and ports before running it.
- Record any script + viewport + date in 04-visual-validation.md.

## 6. After validation
- Stop servers (Ctrl-C).
- Optionally: `rm -rf /tmp/hb-personal-assistant-schedule-ux` (or keep for re-runs).
- cd back to worktree root.
- Run the pre-commit checks:
  ```bash
  cd frontend
  npm run lint
  npm run typecheck
  npm run test
  ```
- From worktree root:
  ```bash
  git status --short
  git diff --stat
  # human review the diff
  git add frontend/src frontend/*.json docs/evidence || true
  git status --short
  git commit -m "fix(schedule): remediate schedule tool navigation and ux hierarchy"
  ```
- **DO NOT PUSH**.
- Record final commit in 03-implementation-summary.md + closeout.

## 7. Rollback (if needed)
```bash
cd /Users/bobbyfetting/hb-personal-assistant
git worktree remove /Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-ux-nav-polish-20260702T154747Z
git branch -D fix/schedule-ux-nav-polish-20260702T154747Z
```

**All steps use only the copied DB. No live mutation.**

**This document + the 00-baseline + terminal logs constitute the operator validation evidence.**
