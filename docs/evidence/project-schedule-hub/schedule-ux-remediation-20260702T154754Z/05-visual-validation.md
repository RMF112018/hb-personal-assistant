# 05-visual-validation.md — Project Schedule UX Remediation

**Stamp**: 20260702T154754Z

## Screenshots captured
`screenshots/` dir created (empty in this commit). Operator to capture the required set during the exact steps in `07-operator-validation-steps.md` (using copied DB + tropical).

Full list + "what each proves" in `02-screenshot-inventory.md`.

All shots **must** use the copied validation DB only.

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
