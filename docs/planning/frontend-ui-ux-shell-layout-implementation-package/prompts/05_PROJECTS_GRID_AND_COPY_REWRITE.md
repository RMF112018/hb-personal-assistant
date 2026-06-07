# P04 — Projects Grid and Project Command-Center Copy

## Objective

Refactor Projects into a production-ready project command-center entry screen using responsive grid/card primitives and business-facing copy.

## Scope

Likely files:

- `frontend/src/pages/ProjectsPage.tsx`
- `frontend/src/pages/ProjectDashboardPage.tsx`
- `frontend/src/components/projects/*`
- shared primitives from P02

## Target layout

```text
Projects
  Page header + primary action / setup guidance
  Dashboard grid:
    Active Projects
    Needs Setup
    Recently Updated
    Project Connections
    All Projects
    Empty State / Setup Guidance
```

## Required copy remediation

Remove implementation/architecture explanations such as:

- domain-nav route explanation;
- read model references;
- source/sync/evidence detail as normal page copy;
- Admin Data Confidence as the default next step for regular users.

Use business-facing copy:

- `Projects that need setup`
- `No active projects are connected yet.`
- `Review project connections in Settings.`
- `Recently updated projects`
- `Project data will appear after sources are connected and approved.`

## Non-scope

- Do not implement live Procore or Graph sync.
- Do not add new project intelligence features beyond layout and setup-readiness surfaces.

## Acceptance criteria

- Projects no longer feels like a route selector.
- Empty/no-project states are visually balanced and actionable.
- Project list/card layout works at desktop/tablet/mobile widths.
- All existing project detail navigation remains reachable.
- Normal UI contains no route/read-model/debug copy.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

Manual smoke:

- Projects with no data.
- Projects with sample/local data.
- Open a project detail page and confirm navigation still works.
