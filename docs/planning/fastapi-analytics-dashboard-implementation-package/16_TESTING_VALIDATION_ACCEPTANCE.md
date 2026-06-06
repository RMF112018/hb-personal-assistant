# Testing, Validation, and Acceptance

## Backend Tests

- FastAPI app imports without optional frontend build.
- OpenAPI generation works.
- All routes are role-guarded.
- Chat routes are absent or disabled/stub-only.
- No raw sensitive fields appear in responses.
- Project URL parsers extract Procore project IDs.
- SharePoint URL classifier detects site vs folder/share link.
- OneDrive scope settings validate.
- Outlook/Calendar project-matching-only is optional and not default.
- Admin-only first sync enforcement works.
- Daily Brief file detector handles missing/current/stale/parse-warning states.

## Frontend Tests

- Primary navigation is CM-first.
- Admin / Data Confidence is secondary.
- No active Chat navigation/page.
- Today renders Daily Brief states.
- Theme dark/light/system works.
- User-facing labels avoid dry-run/apply/execute in primary workflows.

## Acceptance Criteria

- User can complete first-run setup through friendly workflows.
- User can add Procore/SharePoint/OneDrive connections by URL/scope.
- Admin can schedule first sync; non-admin cannot.
- Today view presents actionable content.
- Daily Brief Markdown renders as polished executive brief.
- Admin can troubleshoot data health without dominating primary UX.
