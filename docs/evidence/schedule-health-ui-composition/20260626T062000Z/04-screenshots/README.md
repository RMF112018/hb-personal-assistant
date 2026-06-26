# Screenshot Evidence

Screenshot capture was blocked in this environment.

What was attempted:

- Vite dev server started successfully on `http://127.0.0.1:5178/`.
- Browser control was initialized through the in-app browser tooling.
- The required screenshot payload exists as committed V75 evidence at:
  `docs/evidence/schedule-import-health-foundation/20260626T090621Z/manual-zip-package-proof/TWN.zip/03-health-data.json`
- A reproducible local mock API script was added at:
  `docs/evidence/schedule-health-ui-composition/20260626T062000Z/mock-health-api.mjs`

Blocker:

- The in-app browser API available here does not expose request interception.
- Direct `node` launch of the mock API server was rejected by command policy.

Required screenshots still outstanding:

- Schedule subnav showing `Schedule Health`
- `/schedules/quality` rendering the Schedule Health page
- `/schedules/health` rendering the same page
- Selected schedule version with PM cards above the fold
- Capability panel
- Baseline health section
- Deferred/unavailable analysis section
