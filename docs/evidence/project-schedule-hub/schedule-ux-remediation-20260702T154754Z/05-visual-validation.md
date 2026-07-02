# 05-visual-validation.md — Project Schedule UX Remediation

**Stamp**: 20260702T154754Z

## Screenshots captured
All 9 required screenshots captured and committed against the copied validation DB setup (`HB_ASSISTANT_DB_PATH=/tmp/hb-pa-schedule-ux-final/hb-pa-schedule-ux-20260702T160500Z.sqlite`).

Files:
- schedule-dropdown-closed.png
- schedule-dropdown-open.png
- schedule-overview-top.png
- import-schedule-from-dropdown.png
- review-workbench-from-dropdown.png
- driver-detail-empty-state.png
- activity-drivers-empty-state.png
- baseline-comparison-context.png
- technical-evidence-secondary.png

Stored in `screenshots/`.

See `02-screenshot-inventory.md` for detailed "what each proves".

All shots use the copied validation DB only (no live paths).

## What each proves (summary; see 02 for details + filenames)
- Dropdown closed + open: Schedule tab is grouped nav with all 5 required direct links.
- Overview top: PM story + Primary Actions (Import Schedule prominent Link) lead the page.
- Import / Workbench reached from dropdown: routes discoverable; Schedule group active on nested.
- Baseline section: labels + plain-language explanation of what bases/comparison affect.
- Workbench cards: reduced visible badges, preview/persisted distinction (border), icons on actions.
- Technical/ trends: secondary or collapsed; no jargon in primary story.

## Method + caveats
- Manual browser captures (or adapted prior python+temp-playwright script).
- Viewport: typical desktop (e.g. 1440x900 or full window).
- Theme: dark (default).
- Data: copied DB (confirmed in 00 + 06 steps; no live path).
- Any differences from prod (font subpixel, exact data dates) noted in individual shot metadata if present.

**Visual evidence completes the acceptance criteria (dropdown, import discoverability, hierarchy, active state, polish).**
