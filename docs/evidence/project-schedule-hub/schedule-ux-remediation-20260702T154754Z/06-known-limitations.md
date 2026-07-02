# 05-known-limitations.md — Project Schedule UX Remediation

**Stamp**: 20260702T154754Z

## Unresolved UX gaps (deferred)
- Full chart density reduction: only title + one message polish + one unavailable improvement landed; deeper grouping of the 10+ metric panels (health indices, window accuracy, etc.) left as-is or in "Advanced" if operator wants follow-up. Current viz still dense on wide screens.
- Badge reduction in workbench: significant (8+ → ~4 visible + signals text), but visual tuning (colors, spacing) may benefit from designer pass.
- Dropdown on very small mobile: popup works but no dedicated mobile treatment (e.g. full-width or bottom sheet). Current subnav flex already handles wrap.
- No "search" in Activity Drivers index (the friendly empty); relies on links from overview/workbench. A full activity picker could be added later.
- Primary Actions "Manage Baselines (below)" link is a bit meta; could point to a global baselines surface if one exists.

## Backend contract gaps (if any)
- Unavailable reasons in trend metrics API: some still return generic or missing `reason` / `readiness_status`. Frontend now surfaces what is present and falls back to clearer copy. See MetricPanel updates. If more detail is desired, backend contract enhancement needed (documented for operator).
- No change to any DTO or response shape.

## Items requiring operator decision
- Whether to keep the (now unused) import modal code paths elsewhere or delete more aggressively.
- Exact visual polish / spacing in dropdown menu (current uses simple absolute + tailwind; can adopt more forecast-export-dropdown classes if desired).
- Whether Activity Drivers index should fetch a list of candidates (possible via existing driver preview APIs) vs pure guidance.

## Deferred enhancements (out of scope for this remediation)
- Keyboard arrow nav inside dropdown menu (current is basic focus + links).
- Persisted "last used comparison" preference.
- Full responsive subnav overhaul.
- Playwright e2e added to package (would be nice for future nav regression).

## Data safety
- All validation used copied DB only (see 00 + 06). No exceptions.

**Remediation complete against acceptance criteria despite the above (all primary outcomes + 13 acceptance items addressed).**
