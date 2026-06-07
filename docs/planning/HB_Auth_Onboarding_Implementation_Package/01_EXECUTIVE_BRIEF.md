# Executive Brief

## Objective

Make Microsoft Graph and Procore authentication/onboarding usable from the app while preserving the local-first, no-writeback, construction-management-first product posture.

## Current Repo-Truth Summary Used for This Package

The audit found partial backend primitives but no complete frontend user path.

- Microsoft Graph has backend device-code auth primitives, but the Settings UI does not expose a complete connect/complete/status/re-auth/disconnect flow.
- Procore has backend OAuth start/exchange primitives, but the app does not expose a browser callback or complete frontend OAuth path.
- Project connection preview/save/admin-approval primitives exist at the backend level, but the Settings UI does not provide a full Project Connections workflow.
- The frontend API client exposes Settings GET/PATCH helpers, but not auth start/status/exchange/disconnect, connection preview/save, approval, or data-quality helpers.
- The current frontend dev proxy handles `/api` only, while existing auth/setup backend routes include root-level paths such as `/auth/...`, `/connections/...`, and `/admin/...`.

## Product Outcome

After implementation:

1. First-time unauthenticated users land on `/get-started`.
2. Users can connect Microsoft 365 through a safe local device-code flow.
3. Users can connect Procore through a backend-controlled OAuth flow with localhost callback and manual fallback.
4. Returning users with stale auth get automated refresh attempts before re-auth prompts.
5. Users can preview and save Procore / SharePoint / OneDrive / Outlook / Calendar project-source setup without starting sync.
6. First live sync is blocked until admin approval.
7. Non-admin users see a simple sidebar footer Data Quality indicator with green/yellow/red dot and latest update timestamp on hover.
8. Admin users can inspect detailed auth, readiness, approval, sync freshness, failure, and confidence diagnostics in Settings.

## Implementation Strategy

Use a new normalized route family under `/api/settings/connections/*` and `/api/onboarding/readiness` as the frontend-facing contract. Existing lower-level auth utilities can remain behind these routes. The frontend should not call root-level auth/setup routes directly.

## Primary Architecture Decisions

- Microsoft Graph: MSAL device-code flow as primary local-first auth path.
- Procore: backend-controlled OAuth authorization URL plus localhost callback as primary path; manual authorization-code fallback retained.
- Auth refresh: backend attempts silent/automated refresh at startup/readiness before asking user to re-authenticate.
- Data Quality: safe summary endpoint available to all roles; detailed diagnostics admin-only.
