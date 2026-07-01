# Browser Sign-Off

**STAMP:** 20260701T081419Z  
**Proof type:** live browser (Playwright Chromium)

## Stack

| Service | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8000 | 200 |
| Frontend | http://127.0.0.1:5173 | 200 |

## Post-fix walkthrough

| Step | Result | Screenshot |
|------|--------|------------|
| Schedule hub with anchors + controls | PASS | `post-fix/01-schedule-hub.png` |
| Current Contract Baseline controls context | PASS | `post-fix/02-controls-named-baseline.png` |
| Named Workbench read-only banner | PASS | `post-fix/03-workbench-named-baseline.png` |
| Driver detail slash ID FAB/DEL-10 | PASS | `post-fix/04-driver-detail-slash-activity.png` |
| Missing baseline state | PARTIAL | `post-fix/06-missing-baseline-controls.png` + frontend fixture test (real DB has all slots selected) |
| Back navigation preserves context | PASS | `post-fix/05-back-to-workbench.png` |

## Sign-off answers

| Question | Answer |
|----------|--------|
| PM workflow understandable? | Yes — anchors, comparison context, and read-only preview are explicit |
| Selected named baselines visible? | Yes — anchor cards and comparison lines show date · display name |
| Active comparison basis clear? | Yes — “Comparing against …” on controls, workbench, driver |
| Read-only named preview explained? | Yes — amber banner on workbench |
| Links preserve context? | Yes — `comparison_basis` + `as_of` in URLs |
| Raw IDs demoted? | Yes — activity name is H3; IDs in technical details |
| Advisory posture visible? | Yes — controls + driver footers |
| Before broader PM rollout? | Disposition persistence for named baselines; optional hub section reorder if PM feedback warrants |

## Notes

- Screenshots show live tropical schedule UI for route/PM verification; operational schedule movement data visible.
- Phase 11 slash ID query routing regression covered in `scheduleBaselineLabels.test.ts` + driver page tests.
