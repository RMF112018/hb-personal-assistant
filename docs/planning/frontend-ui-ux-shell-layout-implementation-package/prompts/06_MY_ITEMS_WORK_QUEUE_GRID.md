# P05 — My Items Responsive Work-Queue Grid

## Objective

Refactor My Items into a user-focused work queue with responsive dashboard cards and action-oriented copy.

## Scope

Likely files:

- `frontend/src/pages/MyItemsPage.tsx`
- `frontend/src/components/my-items/*`
- shared primitives from P02

## Target layout

```text
My Items
  Page header
  Dashboard grid:
    My Action Items
    My Meetings
    My Correspondence
    My Files
    My Followed Projects
```

## Required copy remediation

Avoid normal-user copy that over-explains:

- Outlook + Procore + local review state mechanics;
- Graph diagnostics;
- first-sync Admin internals;
- source-system implementation constraints.

Use simple work-queue copy:

- `Items assigned to you or waiting for your review.`
- `No action items need your attention.`
- `Connect Microsoft 365 and Procore in Settings to populate this list.`
- `Waiting for first update approval.`

## Non-scope

- Do not implement new mailbox/calendar/file browser behavior.
- Do not change aggregate API contracts unless tests require type alignment.

## Acceptance criteria

- Action Items has priority placement.
- Cards use shared dashboard/card primitives.
- Empty/loading/error states are source-agnostic and business-readable.
- Normal UI contains no Graph/Admin/diagnostics/source-system implementation copy unless behind a technical disclosure.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

Manual smoke:

- Work queue with empty data.
- Work queue with sample/local data.
- Keyboard order through cards and actions.
