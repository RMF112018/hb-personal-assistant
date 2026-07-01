# Screenshot Wait Gates

**STAMP:** 20260701T081419Z  
**Method:** Playwright Chromium (`capture_pm_walkthrough.py`)  
**Proof type:** live browser

## Loaded-state gates (no screenshot until all pass)

| Shot | Surface | Wait gates |
|------|---------|------------|
| 01 | Schedule hub + Baseline Anchors | No `Loading baseline selections`; three slot labels; `TWNU07/18/14` in anchor `<p>` tags; controls `Comparing against Prior Update` |
| 02 | Schedule Controls (CCB) | No `Loading schedule controls`; `Comparing against Current Contract Baseline · … TWNU07` |
| 03 | Named Workbench | No `Loading schedule workbench`; read-only banner; `Candidate change driver` card |
| 04 | Driver detail FAB/DEL-10 | No `Loading driver detail`; H3 activity name; `Side-by-Side Movement`; comparison context |
| 05 | Back navigation | Workbench link click; URL contains `comparison_basis` + `as_of`; workbench gates |
| 06 | Missing baseline | Playwright route mock for controls API (`baseline_not_selected`); actionable copy visible |

## Manifest

See `screenshot-proof.json` — all shots report `loaded: true`.

## Notes

- Shot 06 uses **mocked API** (no Tropical DB slot mutation).
- Shot 01 scrolls Baseline Anchors into view after controls load to avoid stale loading capture.
