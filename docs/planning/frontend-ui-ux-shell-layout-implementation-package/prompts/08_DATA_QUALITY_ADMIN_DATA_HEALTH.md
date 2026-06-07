# P07 — Sidebar Data Quality and Admin/Data Health Translation

## Objective

Add the non-admin sidebar footer `Data Quality` status indicator and translate Admin/Data Confidence into business-readable Data Health surfaces.

## Scope

Likely files:

- `frontend/src/components/layout/DataQualityIndicator.tsx`
- `frontend/src/components/layout/SidebarFooter.tsx`
- `frontend/src/pages/AdminDataConfidencePage.tsx`
- `frontend/src/lib/statusCopy.ts`
- `frontend/src/hooks/useDataQualitySummary.ts`
- `frontend/src/navigation/navigationModel.ts`

## Required implementation

1. Render a compact `Data Quality` indicator in the pinned sidebar footer for non-admin users.
2. Use green/yellow/red/gray status dot mapping.
3. Reveal latest update date/time and concise status summary on hover and keyboard focus.
4. For admins, route or link to Data Health detail where appropriate.
5. Rename or translate Admin/Data Confidence labels to business-readable copy while preserving route compatibility if needed.
6. Put technical diagnostics behind disclosures.

## Required admin label translations

| Current | Target |
|---|---|
| Source / Sync Health | Source Updates |
| Workflow / Job Health | Background Tasks |
| Evidence / Guardrail Health | Safety Checks |
| Retrieval / AI Quality | Answer Quality |
| Permissions / Governance | Access & Permissions |
| Data Completeness / Coverage | Data Coverage |

## Non-scope

- Do not change actual data-confidence calculations.
- Do not modify admin authorization behavior.
- Do not add external reads or sync jobs.

## Acceptance criteria

- Non-admin users see a simple Data Quality footer indicator.
- Admins see business-readable Data Health, with optional technical detail behind disclosure.
- No local dev role selector instructions appear in admin access-denied states.
- Tooltip/popover is keyboard accessible and readable.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

Manual smoke:

- Viewer shell.
- Operator shell.
- Admin shell.
- Hover and keyboard focus on Data Quality.
- Data unavailable/stale/good/degraded states if fixtures allow.
