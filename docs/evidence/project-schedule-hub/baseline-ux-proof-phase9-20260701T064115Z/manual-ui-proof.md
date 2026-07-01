# Manual UI Proof

**Proof type:** hybrid (automated frontend tests + API fixture proof; live browser not run in agent session)

## Automated UI coverage substituting manual walkthrough

| Step | Evidence |
|---|---|
| Baseline selector visible | `ProjectSchedulePage.test.tsx` — four comparison choices |
| Named controls comparison | `ProjectSchedulePage.test.tsx` — controls basis switching |
| Workbench named URL + no sync | `ProjectScheduleWorkbenchPage.test.tsx` |
| Driver humanized labels | `ProjectScheduleDriverDetailPage.test.tsx` |
| Navigation preserves as_of | Driver unavailable back-link test |
| Workbench/driver link parity | `scheduleBaselineLabels.test.ts` |

## Live UI

Manual browser walkthrough deferred; recommend PM validation on tropical project with fixture or migrated local DB (v96 named slots table).
