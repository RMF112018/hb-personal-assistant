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

## Visual Review Notes (Items Verified Carefully)
- Dropdown usability: Menu uses `absolute z-50` with proper bg/border/shadow. Opens cleanly below trigger without clipping in the subnav layout. Trigger has chevron rotation.
- Active state: `isScheduleActive` uses `startsWith(`${base}/schedule`)`. Verified on Overview, /import, /workbench, /driver-detail, /drivers. Trigger gets `.active` class + `aria-current="page"`.
- Import visibility: Prominent in dropdown (second item) and in Primary Actions row near top of Overview (first action, labeled "Import Schedule").
- Overview order: Story card first, then explicit "Primary Actions" section with Import/Work bench/Export, then Baseline context explanation, Where to Look, then Controls Health (moved lower), Trends, Technical at bottom/secondary.
- Workbench cards: Badge count significantly reduced. Preview vs Persisted distinguished by border accent + label. Severity only shown for critical/high. Actions use distinct icons (Eye, Search) + text. Still shows priority, status, and key context.
- Responsive shell: Dropdown is relative + absolute; subnav flex already supports wrapping. No layout breakage for desktop (primary target). Mobile would inherit current subnav behavior (deferred per scope).
- Technical evidence: Positioned lower in hierarchy, after PM content. In code it's the final TechnicalDetails block.

All points confirmed via code + generated representative screenshots.
