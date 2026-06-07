# 192. Frontend Projects Command Center

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package

## Decision

The Projects entry page uses the shared primary layout, dashboard grid, card, and state primitives as a project command center instead of a route-selector surface. It presents active projects, setup readiness, recently updated projects, project connections, and the all-projects entry in a stable DOM order.

Project detail dashboards keep existing project routes reachable while using business-facing copy for overview, recent movement, items that need attention, and connected-data gaps.

## Rationale

Normal users should not see implementation details, route explanations, read-model language, raw object output, or admin-debug next steps while reviewing project work. Projects surfaces should describe what action is available, where setup belongs, and when connected data will appear.

## Guardrails

- Keep existing project routes and subnav active states intact.
- Do not add backend routes or live sync behavior as part of this layout change.
- Use `safeDisplayText` for object-like fallbacks so raw JSON is not normal page copy.
- Send project setup and connection guidance to Settings.
